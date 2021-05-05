    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.

-------------------------------------------------------------------------------------------------------------------

AlphaTrader is a program intended to execute stock trading signals sent from AlphaHub.us.
Use of this program is at user discretion.

-------------------------------------------------------------------------------------------------------------------

.Net 5.0 Runtime is required to run this program.
		https://dotnet.microsoft.com/download/dotnet/thank-you/runtime-desktop-5.0.5-windows-x64-installer

-------------------------------------------------------------------------------------------------------------------

Installation
	1.  Install .Net 5.0 from the link above
	2.  Extract the zip file to a folder, example : C:\AlphaTrader
	3.  Open AlphaConfiguration.txt and change all the applicable settings
	4.  Open Command line to run the executable
		a.  Windows Start --> type cmd   <enter>
		b.  Path to executable  -->  cd AlphaTrader  <enter>
		c.  Launch program -->  AlphaTrader   <enter>
	5.  Configuration is loaded at startup or if it restarts itself
	6.  Pressing Control-C will end the program or closing the command window

-------------------------------------------------------------------------------------------------------------------

Configuration settings
LOG_PATH -- Path to write log files.  Backslashes '\' must be escaped, ie '\\' and must end with \\
		Example:  C:\\AlphaTrader\\Logs\\       
		Log files are writen out by date and Live/Paper   Example: 20210503_AlphaLog_PAPER.txt

LOG_LEVEL -- All logs written to a text file, potentially the console.
		1 - Console - High importance only
		3 - Normal -  Basic trading information and statuses
		5 - Debug - Very detailed logs

BROKER -- Trading broker
		ALPACA
		TBD - More coming

ACCOUNT_TYPE -- Type of account
		PAPER
		LIVE

API_KEY -- Live API key
API_SECRET -- Live Secret key
PAPER_API_KEY -- Paper API key
PAPER_API_SECRET -- Paper secret key

ALPHA_USERNAME -- Enter your AlphaHub Username
ALPHA_PASSWORD -- Enter your AlphaHub Password

SIGNALS -- Algorithms to subscribe.  Multiple signals can have a , seperating them
		Minotaur1 = 14 | Optimus 1 = 17 | The Optimizer = 18
		Example: 14,17   This would subscribe to both Mino1/Opti1 at 50/50 trade amount

TRADE_AMOUNT -- Amount to trade, total.  This amount would be divided between signals.
				No punctuation in price, no commas.   ALL is valid, example below
		Example:  10000 entered and subscribed to 14,17.  Each signal would get 5000
				  ALL -- 99% of current portfolio value.  Used to reinvest profits.

SLIPPAGE_PERCENT -- Percent checked before executing a market OPEN order.

OPEN_MARKET_ORDER_WAIT -- Time in seconds before canceling limit order and placing BUY/OPEN market order
CLOSE_MARKET_ORDER_WAIT -- Time in seconds before cancling a limit order and playing a SELL/CLOSE market order
		

