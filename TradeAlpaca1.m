clear 

AlpacaPub='  ';% insert keys here
AlpacaPriv='  ';

%alpacaURL = 'https://{api.alpaca.markets}/v2/account';
url= "https://api.alpaca.markets/v2/account"; 

options = weboptions('HeaderFields',{'APCA-API-KEY-ID' AlpacaPub ;'APCA-API-SECRET-KEY' AlpacaPriv} )
data = webread(url,options)
url_positions="https://api.alpaca.markets/v2/positions"; 
data2=webread(url_positions,options)


tradeON=0;
if tradeON==1
url_orders="https://api.alpaca.markets/v2/orders"; 
symbol='IDXX';
limit_price='508.68';
qty='22';
side='sell';
time_in_force='day';
type='limit';

options = weboptions('HeaderFields',{'APCA-API-KEY-ID' AlpacaPub;'APCA-API-SECRET-KEY' AlpacaPriv},'MediaType', 'application/json');
data1 = struct('symbol', symbol, 'qty', qty, 'side', side, 'type', type, 'time_in_force', time_in_force,'limit_price', limit_price);
responseTr = webwrite(url_orders, data1, options)
end


%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% ORDERS
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
url_orders= "https://api.alpaca.markets/v2/orders";
dataAlpacaOrders=webread(url_orders,options)


cancel1=0;

if cancel1==1
 for i=1:length(dataAlpacaOrders)

            symbol=dataAlpacaOrders(i).symbol
            qty=dataAlpacaOrders(i).qty;
            orderID=dataAlpacaOrders(i).id
            side=dataAlpacaOrders(i).side;
            %send closing order at MARKET
            formatSpec1 ="https://api.alpaca.markets/v2/orders%s%s";
            A1='/';
            A2=orderID;
            url_delete= sprintf(formatSpec1,A1,A2);
            time_in_force='day';
            type='market';
            %respose=webwrite(url_orders,options)
            options = weboptions('HeaderFields',{'APCA-API-KEY-ID' AlpacaPub ;'APCA-API-SECRET-KEY' AlpacaPriv},'MediaType', 'application/x-www-form-urlencoded','RequestMethod','delete');
     
            data1 = struct('type', type, 'time_in_force', time_in_force);
            responseDelete = webwrite(url_delete, options)
          

 end
 
end




    