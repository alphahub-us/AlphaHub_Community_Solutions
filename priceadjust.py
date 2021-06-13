import abc
import collections
from decimal import Decimal
import math

from blade import config
from blade import order


class _Adjuster(abc.ABC):
    def __init__(self, c):
        self.c = c
        self.all_orders = set()
        self.pending_orders = []

    def register(self, orders):
        for o in orders:
            self.c.log(
                "To %s: %d %s @ %f"
                % (o.verb, o.amount, o.asset, o.target_price)
            )
        self.all_orders = orders

    def get_orders(self, tick):
        return {o for o in self.all_orders if o.amount > 0}

    @abc.abstractmethod
    def adjust(self, o, tick):
        raise NotImplementedError


# stick to target price
class _Target(_Adjuster):
    def adjust(self, o, tick):
        o.desired_price = self.c.adjust_price(o.asset, o.target_price)


# todo: this adjuster should consider that cancellation may take a while / fail
# to avoid double buy / double sell
# stick to ticker price
class _Ticker(_Adjuster):
    def adjust(self, o, tick):
        o.desired_price = self.c.adjust_price(o.asset, tick[o.asset])


# stick to ticker price
class _AskBid(_Adjuster):
    def register(self, orders):
        super().register(orders)
        self.pending_orders = []

    def adjust(self, o, tick):
        if o._to_cancel:
            return
        if o.is_sell():
            o.desired_price = self.c.adjust_price(
                o.asset, self.c.get_bid(o.asset)
            )
        else:
            o.desired_price = self.c.adjust_price(
                o.asset, self.c.get_ask(o.asset)
            )

    def _get_limit_order(self, asset):
        for o in self.pending_orders:
            if o.asset == asset and not o._accounted_for:
                return o

    def _get_original_order(self, asset):
        for o in self.all_orders:
            if o.asset == asset:
                return o

    def _account_for_completed_orders(self):
        filled_assets = set()

        def register_filled(asset, filled):
            orig_order = self._get_original_order(asset)
            orig_order.filled += filled
            if filled > 0:
                filled_assets.add(asset)

        for o in set(self.pending_orders):
            if not o._accounted_for:
                if o.completed:
                    register_filled(o.asset, o.filled)
                    o._accounted_for = True
                elif o._to_cancel and not o.posted:
                    register_filled(o.asset, o.filled)
                    self.pending_orders.remove(o)

    def do_trade(self, o, tick):
        return True

    def get_orders(self, tick):
        self._account_for_completed_orders()

        for o in self.all_orders:
            self.c.log(
                "%s executed at: %.2f (%d/%d)"
                % (o.asset, o.filled / o.amount * 100, o.filled, o.amount)
            )

            if not self.do_trade(o, tick):
                continue

            # original order is used for accounting purposes to carry
            # information about remaining assets to trade
            orig_order = self._get_original_order(o.asset)

            # prepare the new order candidate
            new_order = orig_order.__class__(
                o.asset,
                orig_order.remaining,
                orig_order.target_price,
                time_cb=orig_order.time_cb,
                otype=order.LIMIT_ORDER,
            )

            # make sure the price we use to determine if we need to cancel
            # an existing order is already adjusted to avoid unnecessary
            # cancels
            self.adjust(new_order, tick)

            lo = self._get_limit_order(o.asset)
            if lo is None:
                # post new order only if the old one is gone
                self.pending_orders.append(new_order)
            else:
                if lo.actual_price != new_order.desired_price:
                    # first cancel existing order
                    lo.desired_price = None
                    lo._to_cancel = True

        return {o for o in self.pending_orders if o.amount > 0}


class _WaitNSee(_AskBid):
    def register(self, orders):
        super().register(orders)
        self._delta = collections.defaultdict(lambda: None)

    def _get_any_original_order(self):
        for o in self.all_orders:
            return o

    @property
    def remaining_time(self):
        o = self._get_any_original_order()
        if o is None:
            return Decimal(0)

        # todo: expose _start_time to public
        time_passed = o.time_cb() - o._start_time
        return Decimal(self.c.trading_interval - time_passed.total_seconds())

    def do_trade(self, o, tick):
        asset = o.asset
        if self._delta[asset] is None:
            if self.remaining_time <= self.c.trading_interval - 46 * 2:
                self._delta[asset] = (
                    tick[asset] - o.target_price
                ) / o.target_price
                if o.is_sell():
                    self._delta[asset] *= -1
        if self._delta[asset] is None:
            return False
        if self._delta[asset] >= 0:
            return True
        if self.remaining_time <= 10:
            return True
        return False


m1 = Decimal("0.0001")
m2 = Decimal("0.0003")
g1 = Decimal("0.0000")
as1 = Decimal("0.65")
as2 = Decimal(1)
mul = Decimal("1.0")


# dynamically move price in layers
class _DynLayers(_Adjuster):
    LAYERS = (3, 2, 4, 1, 5)  # in order of preference
    STOP_LOSS_LAYERS = (5,)
    STOP_LOSS_TO_LIMIT_LAYER = 3

    LAYER_WEIGHTS = {
        1: Decimal("0.02"),
        2: Decimal("0.10"),
        3: Decimal("0.10"),
        4: Decimal("0.30"),
        5: Decimal("0.48"),
    }
    LAYER_ABS_SKEWS = {
        1: -as2 * mul * m2,
        2: -as2 * m2,
        3: as1 * m1,
        4: as1 * mul * m1 - g1,
        5: as1 * mul * m1,
    }
    # at the moment, we split into just two - unequal - pieces (or one, if the
    # smaller piece is too small / empty after adjustment)
    SPLIT_FACTOR = Decimal(1.2)

    @classmethod
    def _split_amount(cls, amount):
        # todo: int() application is Robinhood / stocks specific
        first = Decimal(int(amount / cls.SPLIT_FACTOR))
        yield first
        if first != amount:
            yield amount - first

    def _get_chunk_of(self, o, layer):
        chunk = o.amount * self.LAYER_WEIGHTS[layer]
        chunk_diff = chunk if o.is_buy() else -chunk
        return abs(self.c.adjust_amount(o.asset, chunk_diff, self.c.ticker()))

    @classmethod
    def _layer_to_order_type(cls, layer):
        if layer in cls.STOP_LOSS_LAYERS:
            return order.STOP_LOSS_ORDER
        return order.LIMIT_ORDER

    @staticmethod
    def _initialize_layer(o, layer):
        o.layer = layer
        o._layer_locked = False

    def _split(self, o):
        res = []
        remaining = o.amount
        for layer in self.LAYERS:
            # calculate intended size of the layer chunk of the original order
            amount = self._get_chunk_of(o, layer)
            # cap chunk size by requested amount
            amount = min(remaining, amount)
            if amount == 0:
                continue
            # split the chunk into more pieces
            for amount in self._split_amount(amount):
                new_order = o.__class__(
                    o.asset,
                    amount,
                    o.target_price,
                    time_cb=o.time_cb,
                    otype=self._layer_to_order_type(layer),
                )
                self._initialize_layer(new_order, layer)
                res.append(new_order)
                remaining -= amount

        # if all chunks were too small, return the original order
        if not res:
            self._initialize_layer(o, self.LAYERS[0])
            return set([o])

        # add the rest to the highest priority order
        if remaining > 0:
            res[0].amount += remaining

        return set(res)

    def register(self, orders):
        super().register(orders)
        all_orders = set(self.all_orders)
        self.all_orders = set()
        for o in all_orders:
            self.all_orders |= self._split(o)
        # sort orders from smaller to larger; we'd like to test waters first
        # before posting our larger pieces
        self.all_orders = list(
            sorted(
                [o for o in self.all_orders if not o.completed],
                key=lambda o: (o.amount, o.layer),
            )
        )
        return self.all_orders

    @staticmethod
    def _round_with(price, func):
        return func(price * Decimal(100)) / Decimal(100)

    def _adjust_to_better(self, verb, price):
        return self._round_with(
            price, math.floor if verb == "buy" else math.ceil
        )

    def _adjust_to_layer(self, o, tick):
        skew = Decimal(1) + self.LAYER_ABS_SKEWS[o.layer]
        anchor = tick[o.asset]
        if o.is_buy():
            price = anchor * skew
        else:
            price = anchor / skew
        return self._adjust_to_better(o.verb, price)

    def _get_peers(self, o):
        return {
            other
            for other in self.all_orders
            if other.asset == o.asset and other is not o
        }

    def _get_pending_peers(self, o):
        return {other for other in self._get_peers(o) if not other.completed}

    def _peer_posted(self, o):
        return any(
            p.posted and p.layer == o.layer for p in self._get_pending_peers(o)
        )

    def _pending_peers_present_in_limit_order_layers(self, o):
        for peer in self._get_pending_peers(o):
            if peer.layer not in self.STOP_LOSS_LAYERS:
                return True
        return False

    def _pending_peers_present_in_higher_layer(self, o):
        for peer in self._get_pending_peers(o):
            if peer.layer == o.layer + 1:
                return True
        return False

    @classmethod
    def _is_highest_limit_order_layer(cls, layer):
        return layer == max(set(cls.LAYERS) - set(cls.STOP_LOSS_LAYERS))

    def _adjust_layer(self, o):
        # move the last standing stop loss orders down
        if o.layer in self.STOP_LOSS_LAYERS:
            if not self._pending_peers_present_in_limit_order_layers(o):
                o.layer = self.STOP_LOSS_TO_LIMIT_LAYER
                o._layer_locked = True
        # bubble up limit orders if higher layers are empty
        else:
            if not self._is_highest_limit_order_layer(o.layer):
                if not self._pending_peers_present_in_higher_layer(o):
                    o.layer += 1
        # update order type in case layer type changed
        o.desired_type = self._layer_to_order_type(o.layer)

    def adjust(self, o, tick):
        if self._peer_posted(o):
            o.desired_price = None
            return
        if not o._layer_locked:
            self._adjust_layer(o)
        o.desired_price = self.c.adjust_price(
            o.asset, self._adjust_to_layer(o, tick)
        )


class _Delta(_Adjuster):
    DELTA_SECTION = "delta"

    @property
    def GracePeriod(self):
        return config.get_from_config(
            key="GracePeriod", section=self.DELTA_SECTION, factory=int
        )

    @property
    def ParN1(self):
        return config.get_from_config(
            key="ParN1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def expN1(self):
        return config.get_from_config(
            key="expN1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def denN1(self):
        return config.get_from_config(
            key="denN1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def ParZ(self):
        return config.get_from_config(
            key="ParZ", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def ParP(self):
        return config.get_from_config(
            key="ParP", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def expP1(self):
        return config.get_from_config(
            key="expP1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def amount_threshold(self):
        return config.get_from_config(
            key="amount_threshold", section=self.DELTA_SECTION, factory=float
        )

    @property
    def price_threshold(self):
        return config.get_from_config(
            key="price_threshold", section=self.DELTA_SECTION, factory=float
        )

    @property
    def A1(self):
        return config.get_from_config(
            key="A1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def L1(self):
        return config.get_from_config(
            key="L1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def L2(self):
        return config.get_from_config(
            key="L2", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def delta_bad_cap(self):
        return config.get_from_config(
            key="delta_bad_cap", section=self.DELTA_SECTION, factory=float
        )

    @property
    def delta_good_cap(self):
        return config.get_from_config(
            key="delta_good_cap", section=self.DELTA_SECTION, factory=float
        )

    def __init__(self, c):
        super().__init__(c)
        self.pending_orders = []

    def register(self, orders):
        super().register(orders)
        self.pending_orders = []

    def _get_any_original_order(self):
        for o in self.all_orders:
            return o

    @property
    def time_is_up(self):
        return self.remaining_time < self.GracePeriod

    @property
    def remaining_time(self):
        o = self._get_any_original_order()
        if o is None:
            return Decimal(0)

        # todo: expose _start_time to public
        time_passed = o.time_cb() - o._start_time
        return Decimal(self.c.trading_interval - time_passed.total_seconds())

    @staticmethod
    def _round_with(price, func):
        return func(price * Decimal(100)) / Decimal(100)

    def _adjust_to_better(self, verb, price):
        return self._round_with(
            price, math.ceil if verb == "sell" else math.floor
        )

    def _adjust_to_worse(self, verb, price):
        return self._round_with(
            price, math.floor if verb == "sell" else math.ceil
        )

    def adjust(self, o, tick):
        if o._to_cancel:
            return
        price = self.c.adjust_price(o.asset, tick[o.asset])
        if o.type == order.LIMIT_ORDER:
            if self.c.is_wild_price_move(o.asset, o.is_buy()):
                o.add_flag("wild")
                if o.is_buy():
                    price = self.c.adjust_price(
                        o.asset, self.c.get_ask(o.asset)
                    )
                else:
                    price = self.c.adjust_price(
                        o.asset, self.c.get_bid(o.asset)
                    )
                o.desired_price = self._adjust_to_worse(o.verb, price)
            else:
                o.remove_flag("wild")
                if self.time_is_up:
                    o.desired_price = self._adjust_to_worse(o.verb, price)
                else:
                    o.desired_price = self._adjust_to_better(o.verb, price)
        else:
            o.desired_price = self._adjust_to_worse(o.verb, price)

    def _get_limit_order(self, asset):
        for o in self.pending_orders:
            if o.asset == asset and not o._stop_loss and not o._accounted_for:
                return o

    def _get_stop_limit_order(self, asset):
        for o in self.pending_orders:
            if o.asset == asset and o._stop_loss and not o._accounted_for:
                return o

    def _get_original_order(self, asset):
        for o in self.all_orders:
            if o.asset == asset:
                return o

    def _get_delta(self, asset, tick):
        orig_order = self._get_original_order(asset)
        delta = (
            (tick[asset] - orig_order.target_price)
            / orig_order.target_price
            * Decimal(100)
        )
        if orig_order.verb == "sell":
            return -delta
        return delta

    def _to_trade(self, asset, tick):
        orig_order = self._get_original_order(asset)
        delta = self._get_delta(asset, tick)
        min_amount = Decimal(1)
        v_t = self.A1 * (
            (orig_order.remaining / orig_order.amount) ** self.L1
            # make sure we don't ever divide by zero
            / (max(Decimal(1), self.remaining_time) / 2) ** self.L2
        )
        if delta > self.delta_bad_cap:
            S1 = S2 = Decimal(0)
            min_amount = Decimal(0)
        elif delta < self.delta_good_cap or self.time_is_up:
            S1 = Decimal(1)
            S2 = Decimal(0)
        elif delta < 0:
            S1 = max(v_t, self.ParN1 * abs(delta) ** self.expN1 / self.denN1)
            S2 = Decimal(0)
        elif delta == 0:
            S1 = max(v_t, self.ParZ)
            S2 = Decimal(0)
        else:
            S1 = S2 = max(
                v_t, self.ParP * abs(delta) ** self.expP1 / self.denN1
            )

        S1 = min(
            orig_order.remaining,
            max(
                min_amount,
                abs(
                    self.c.adjust_amount(
                        asset, S1 * orig_order.amount, self.c.ticker()
                    )
                ),
            ),
        )
        if S2 > 0:
            S2 = min(
                orig_order.remaining - S1,
                max(
                    min_amount,
                    abs(
                        self.c.adjust_amount(
                            asset, S2 * orig_order.amount, self.c.ticker()
                        )
                    ),
                ),
            )
        else:
            S2 = min(
                orig_order.remaining - S1,
                abs(
                    self.c.adjust_amount(
                        asset, S2 * orig_order.amount, self.c.ticker()
                    )
                ),
            )
        # todo: consider allowing stop loss orders
        S2 = Decimal(0)
        rem = orig_order.remaining - S1 - S2

        return S1, S2, rem

    def _account_for_completed_orders(self):
        def register_filled(asset, filled):
            orig_order = self._get_original_order(asset)
            orig_order.filled += filled

        for o in set(self.pending_orders):
            if not o._accounted_for:
                if o.completed:
                    register_filled(o.asset, o.filled)
                    o._accounted_for = True
                elif o._to_cancel and not o.posted:
                    register_filled(o.asset, o.filled)
                    self.pending_orders.remove(o)

    def get_orders(self, tick):
        self._account_for_completed_orders()

        for o in self.all_orders:
            self.c.log(
                "%s executed at: %.2f (%d/%d)"
                % (o.asset, o.filled / o.amount * 100, o.filled, o.amount)
            )

            limit_to_trade, stop_loss_to_trade, rem = self._to_trade(
                o.asset, tick
            )

            # original order is used for accounting purposes to carry
            # information about remaining assets to trade
            orig_order = self._get_original_order(o.asset)

            lo = self._get_limit_order(o.asset)
            if limit_to_trade == 0:
                # nothing to trade; cancel existing order if any
                if lo is not None:
                    lo.desired_price = None
                    lo._to_cancel = True
                    rem -= lo.amount
            else:
                # prepare the new order candidate
                new_order = orig_order.__class__(
                    o.asset,
                    limit_to_trade,
                    orig_order.target_price,
                    time_cb=orig_order.time_cb,
                    otype=order.LIMIT_ORDER,
                )
                new_order._stop_loss = False

                # make sure the price we use to determine if we need to cancel
                # an existing order is already adjusted to avoid unnecessary
                # cancels
                self.adjust(new_order, tick)

                if lo is None:
                    # post new order only if the old one is gone
                    self.pending_orders.append(new_order)
                else:
                    # if the amount or price is different, cancel the order
                    # this iteration; the next iteration we'll revisit the spot
                    # price and perhaps post the new order
                    if (
                        lo.amount != limit_to_trade
                        or lo.actual_price != new_order.desired_price
                        or lo.type != order.LIMIT_ORDER
                    ):
                        amount_change = (
                            abs(lo.amount - limit_to_trade) / orig_order.amount
                        )
                        if lo.actual_price and new_order.desired_price:
                            price_change = (
                                abs(lo.actual_price - new_order.desired_price)
                                / lo.target_price
                            )
                        else:
                            price_change = 1.0
                        negligent_change = (
                            lo.actual_price == new_order.desired_price
                            and amount_change < self.amount_threshold
                        ) or (
                            lo.amount == new_order.amount
                            and price_change < self.price_threshold
                        )
                        if not negligent_change:
                            lo.desired_price = None
                            lo._to_cancel = True
                            rem -= lo.amount

            slo = self._get_stop_limit_order(o.asset)
            if stop_loss_to_trade == 0:
                # nothing to trade; cancel existing order if any
                if slo is not None:
                    slo.desired_price = None
                    slo._to_cancel = True
                    rem -= slo.amount
            else:
                # prepare the new order candidate
                new_order = orig_order.__class__(
                    o.asset,
                    stop_loss_to_trade,
                    orig_order.target_price,
                    time_cb=orig_order.time_cb,
                    otype=order.STOP_LOSS_ORDER,
                )
                new_order._stop_loss = True

                # make sure the price we use to determine if we need to cancel
                # an existing order is already adjusted to avoid unnecessary
                # cancels
                self.adjust(new_order, tick)

                if slo is None:
                    # post new order only if the old one is gone
                    self.pending_orders.append(new_order)
                else:
                    # if the amount or price is different, cancel the order
                    # this iteration; the next iteration we'll revisit the spot
                    # price and perhaps post the new order
                    if (
                        slo.amount != stop_loss_to_trade
                        or slo.actual_price != new_order.desired_price
                        or slo.type != order.STOP_LOSS_ORDER
                    ):
                        amount_change = (
                            abs(slo.amount - limit_to_trade)
                            / orig_order.amount
                        )
                        if slo.actual_price and new_order.desired_price:
                            price_change = (
                                abs(slo.actual_price - new_order.desired_price)
                                / slo.target_price
                            )
                        else:
                            price_change = 1.0
                        negligent_change = (
                            slo.actual_price == new_order.desired_price
                            and amount_change < self.amount_threshold
                        ) or (
                            slo.amount == new_order.amount
                            and price_change < self.price_threshold
                        )
                        if not negligent_change:
                            slo.desired_price = None
                            slo._to_cancel = True
                            rem -= slo.amount

            rem_order = orig_order.__class__(
                o.asset,
                rem,
                orig_order.target_price,
                time_cb=orig_order.time_cb,
            )
            rem_order.desired_price = None
            rem_order._to_cancel = True
            self.pending_orders.append(rem_order)

        return {o for o in self.pending_orders if o.amount > 0}


class _NewDelta(_Adjuster):
    DELTA_SECTION = "newdelta"

    @property
    def ParN1(self):
        return config.get_from_config(
            key="ParN1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def expN1(self):
        return config.get_from_config(
            key="expN1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def ParZ(self):
        return config.get_from_config(
            key="ParZ", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def ParP1(self):
        return config.get_from_config(
            key="ParP1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def expP1(self):
        return config.get_from_config(
            key="expP1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def amount_threshold(self):
        return config.get_from_config(
            key="amount_threshold", section=self.DELTA_SECTION, factory=float
        )

    @property
    def price_threshold(self):
        return config.get_from_config(
            key="price_threshold", section=self.DELTA_SECTION, factory=float
        )

    @property
    def A1(self):
        return config.get_from_config(
            key="A1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def A2(self):
        return config.get_from_config(
            key="A2", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def A3(self):
        return config.get_from_config(
            key="A3", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def L1(self):
        return config.get_from_config(
            key="L1", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def L2(self):
        return config.get_from_config(
            key="L2", section=self.DELTA_SECTION, factory=Decimal
        )

    @property
    def delta_bad_cap(self):
        return config.get_from_config(
            key="delta_bad_cap", section=self.DELTA_SECTION, factory=float
        )

    def __init__(self, c):
        super().__init__(c)
        self.pending_orders = []

    def register(self, orders):
        super().register(orders)
        self.pending_orders = []
        self.count1 = {o.asset: 1 for o in orders}

    def _get_any_original_order(self):
        for o in self.all_orders:
            return o

    @property
    def remaining_time(self):
        o = self._get_any_original_order()
        if o is None:
            return Decimal(0)

        # todo: expose _start_time to public
        time_passed = o.time_cb() - o._start_time
        return Decimal(self.c.trading_interval - time_passed.total_seconds())

    @staticmethod
    def _round_with(price, func):
        return func(price * Decimal(100)) / Decimal(100)

    def _adjust_to_better(self, verb, price):
        return self._round_with(
            price, math.ceil if verb == "sell" else math.floor
        )

    def adjust(self, o, tick):
        if o._to_cancel:
            return
        price = self.c.adjust_price(o.asset, tick[o.asset])
        o.desired_price = self._adjust_to_better(o.verb, price)

        delta = self._get_delta(o.asset, tick)
        if delta > 0:
            if o.is_buy():
                # todo: don't hardcode one penny
                o.desired_price = o.desired_price - Decimal("0.01")
            else:
                o.desired_price = o.desired_price + Decimal("0.01")

        if o.is_buy():
            ask_price = self.c.get_ask(o.asset)
            d1 = (ask_price - price) / price * 100
            if d1 < 0.005:
                price = self.c.adjust_price(o.asset, ask_price)
                o.desired_price = self._adjust_to_better(o.verb, price)
        else:
            bid_price = self.c.get_bid(o.asset)
            d1 = (price - bid_price) / price * 100
            if d1 < 0.005:
                price = self.c.adjust_price(o.asset, bid_price)
                o.desired_price = self._adjust_to_better(o.verb, price)

    def _get_limit_order(self, asset):
        for o in self.pending_orders:
            if o.asset == asset and not o._accounted_for:
                return o

    def _get_original_order(self, asset):
        for o in self.all_orders:
            if o.asset == asset:
                return o

    def _get_delta(self, asset, tick):
        orig_order = self._get_original_order(asset)
        delta = (
            (tick[asset] - orig_order.target_price)
            / orig_order.target_price
            * Decimal(100)
        )
        if orig_order.verb == "sell":
            return -delta
        return delta

    def _to_trade(self, asset, tick):
        orig_order = self._get_original_order(asset)
        delta = self._get_delta(asset, tick)
        min_amount = Decimal(1)
        v_t = (
            self.A1
            * (orig_order.remaining / orig_order.amount) ** self.L1
            # make sure we don't ever divide by zero
            / (self.A2 * (max(Decimal(1), self.remaining_time) / 2) ** self.L2)
            * self.A3
            * self.count1[asset]
        ) / orig_order.amount
        if delta < 0:
            S1 = max(v_t, self.ParN1 * abs(delta) ** self.expN1)
        elif delta == 0:
            S1 = self.ParZ
        elif delta > 0:
            S1 = max(v_t, self.ParP1 * abs(delta) ** self.expP1)
            if delta > self.delta_bad_cap:
                S1 = Decimal(0)

        if S1 > 0:
            S1 = min(
                orig_order.remaining,
                max(
                    min_amount,
                    abs(
                        self.c.adjust_amount(
                            asset, S1 * orig_order.amount, self.c.ticker()
                        )
                    ),
                ),
            )
        return S1, orig_order.remaining - S1

    def _account_for_completed_orders(self):
        filled_assets = set()

        def register_filled(asset, filled):
            orig_order = self._get_original_order(asset)
            orig_order.filled += filled
            if filled > 0:
                filled_assets.add(asset)

        for o in set(self.pending_orders):
            if not o._accounted_for:
                if o.completed:
                    register_filled(o.asset, o.filled)
                    o._accounted_for = True
                elif o._to_cancel and not o.posted:
                    register_filled(o.asset, o.filled)
                    self.pending_orders.remove(o)

        for k in self.count1:
            if k not in filled_assets:
                self.count1[k] += 1

    def get_orders(self, tick):
        self._account_for_completed_orders()

        for o in self.all_orders:
            self.c.log(
                "%s executed at: %.2f (%d/%d)"
                % (o.asset, o.filled / o.amount * 100, o.filled, o.amount)
            )

            limit_to_trade, rem = self._to_trade(o.asset, tick)

            # original order is used for accounting purposes to carry
            # information about remaining assets to trade
            orig_order = self._get_original_order(o.asset)

            lo = self._get_limit_order(o.asset)
            if limit_to_trade == 0:
                # nothing to trade; cancel existing order if any
                if lo is not None:
                    lo.desired_price = None
                    lo._to_cancel = True
                    rem -= lo.amount
            else:
                # prepare the new order candidate
                new_order = orig_order.__class__(
                    o.asset,
                    limit_to_trade,
                    orig_order.target_price,
                    time_cb=orig_order.time_cb,
                    otype=order.LIMIT_ORDER,
                )

                # make sure the price we use to determine if we need to cancel
                # an existing order is already adjusted to avoid unnecessary
                # cancels
                self.adjust(new_order, tick)

                if lo is None:
                    # post new order only if the old one is gone
                    self.pending_orders.append(new_order)
                else:
                    # if the amount or price is different, cancel the order
                    # this iteration; the next iteration we'll revisit the spot
                    # price and perhaps post the new order
                    if (
                        lo.amount != limit_to_trade
                        or lo.actual_price != new_order.desired_price
                        or lo.type != order.LIMIT_ORDER
                    ):
                        amount_change = (
                            abs(lo.amount - limit_to_trade) / orig_order.amount
                        )
                        if lo.actual_price and new_order.desired_price:
                            price_change = (
                                abs(lo.actual_price - new_order.desired_price)
                                / lo.target_price
                            )
                        else:
                            price_change = 1.0
                        negligent_change = (
                            lo.actual_price == new_order.desired_price
                            and amount_change < self.amount_threshold
                        ) or (
                            lo.amount == new_order.amount
                            and price_change < self.price_threshold
                        )
                        if not negligent_change:
                            lo.desired_price = None
                            lo._to_cancel = True
                            rem -= lo.amount

            rem_order = orig_order.__class__(
                o.asset,
                rem,
                orig_order.target_price,
                time_cb=orig_order.time_cb,
            )
            rem_order.desired_price = None
            rem_order._to_cancel = True
            self.pending_orders.append(rem_order)

        return {o for o in self.pending_orders if o.amount > 0}


_RULES = {
    "target": _Target,
    "ticker": _Ticker,
    "dynlayers": _DynLayers,
    "delta": _Delta,
    "newdelta": _NewDelta,
    "askbid": _AskBid,
    "waitnsee": _WaitNSee,
}
_default_rules = "delta"


def get_rules(name=None):
    if name is None:
        return _RULES.get(_default_rules)
    return _RULES[name]
