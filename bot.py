import asyncio
import aiohttp
import telegram
from datetime import datetime
import logging
from typing import Dict, List, Set
import json
from asyncio import TimeoutError
from aiohttp import ClientError
import backoff
import certifi
import ssl

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JupiterArbitrageBot: # this class will be used to create an instance of the bot
    def __init__(self, config: Dict):   #   Initialize the bot with the configuration
        self.min_profit_percent = config.get('min_profit_percent', 1.0)     #   Get the minimum profit percent from the config
        self.min_liquidity = config.get('min_liquidity', 10000)   #   Get the minimum liquidity from the config
        self.telegram_bot = telegram.Bot(token=config['telegram_token'])    #   Initialize the Telegram bot
        self.telegram_chat_id = config['telegram_chat_id']  #   Get the Telegram chat ID from the config
        self.base_url = ''   #   Set the base URL for the Jupiter API
        self.tokens = []    #   Initialize the tokens list
        self.is_running = False    #   Initialize the running status of the bot to false
        self.blacklisted_tokens: Set[str] = set()   #   Initialize the blacklisted tokens set
        self.session = None #   Initialize the aiohttp session

    async def initialize(self): 
        """Initialize aiohttp session and fetch viable tokens."""
        connector = aiohttp.TCPConnector(ssl=False)
        self.session = aiohttp.ClientSession(connector=connector)
        try:    #   Try to fetch the tokens from the Jupiter API
            print("Fetching tokens from Jupiter API...")
            async with self.session.get('https://token.jup.ag/all') as response:    #   Make a GET request to the Jupiter API
                print(f"Response status: {response.status}")    #   Print the response status
                tokens = await response.json()  #   Get the JSON response
                
                # Debug first few tokens
                print("Sample raw tokens:")
                for token in tokens[:3]:    #   Print the first 3 tokens
                    print(f"Token: {token}")
                # Filter tokens with decimals and common symbols
                self.tokens = [
                    token for token in tokens[:20]  # Start with top 20 tokens
                    if token.get('decimals', 0) > 0     # Filter tokens with decimals
                    and token.get('symbol') in ['SOL', 'USDC', 'USDT', 'ETH', 'BONK']  # Common tokens
                ]
                
                logger.info(f"Total tokens before filtering: {len(tokens)}")    #   Log the total number of tokens before filtering
                logger.info(f"Tokens after filtering: {len(self.tokens)}")  #   Log the total number of tokens after filtering
                logger.info(f"Sample filtered tokens: {self.tokens[:3]}")   #   Log the first 3 filtered tokens
        except Exception as e:  #   Handle exceptions
            logger.error(f"Error initializing tokens: {e}")
            raise

    async def get_price_quote(self, input_mint: str, output_mint: str, amount: int) -> Dict: 
        """Get price quote from Jupiter API."""
        try:
            url = f"{self.base_url}/quote"  #   Set the URL for the quote endpoint
            params = {  #   Set the parameters for the request
                'inputMint': input_mint,
                'outputMint': output_mint,
                'amount': str(amount)
            }
            
            async with self.session.get(url, params=params, timeout=10) as response:    #   Make a GET request to the Jupiter API
                if response.status == 404:  #   Handle 404 status code
                    self.blacklisted_tokens.add(input_mint)     #   Add the input mint to the blacklisted tokens
                    self.blacklisted_tokens.add(output_mint)    #   Add the output mint to the blacklisted tokens
                    return None
                    
                if response.status != 200:  #   Handle non-200 status codes
                    return None
                
                return await response.json()    #   Return the JSON response
                
        except Exception as e:
            logger.error(f"Error getting price quote: {e}")
            return None

    async def check_arbitrage(self, token1: Dict, token2: Dict) -> Dict:
        """Check for arbitrage opportunity between two tokens."""
        if token1['address'] in self.blacklisted_tokens or token2['address'] in self.blacklisted_tokens:    #   Check if the tokens are blacklisted
            return None

        if token1['symbol'] in ['USDC', 'USDT']:    #   Set the initial amount based on the token symbol
            initial_amount = int(100 * (10 ** 6))  # $100.00 USDC/USDT
        elif token1['symbol'] == 'SOL':    #   Set the initial amount based on the token symbol
            initial_amount = int(1.5 * (10 ** 9))  # 1.5 SOL
        else:
            initial_amount = int(1 * (10 ** token1['decimals']))

        logger.info(f"Checking pair: {token1['symbol']} - {token2['symbol']}")      #   Log the pair being checked
        logger.info(f"Initial amount: {initial_amount} {token1['symbol']}")   #   Log the initial amount

        forward_quote = await self.get_price_quote(token1['address'], token2['address'], initial_amount)    #   Get the forward quote
        if not forward_quote:
            logger.error(f"Failed to get forward quote for {token1['symbol']} -> {token2['symbol']}")   #   Log the error
            return None

        backward_quote = await self.get_price_quote(token2['address'], token1['address'], forward_quote['outAmount'])   #   Get the backward quote
        if not backward_quote:
            logger.error(f"Failed to get backward quote for {token2['symbol']} -> {token1['symbol']}")  #   Log the error
            return None

        profit = int(backward_quote['outAmount']) - initial_amount  #   Calculate the profit
        profit_percent = (profit / initial_amount) * 100    #   Calculate the profit percent

        if profit_percent > self.min_profit_percent:    #   Check if the profit percent is greater than the minimum profit percent
            return {
                'token1_symbol': token1['symbol'],
                'token2_symbol': token2['symbol'],
                'profit': profit,
                'profit_percent': profit_percent,
                'usd_value': (profit / (10 ** token1['decimals'])) * float(token1.get('usdValue', 0)),
                'routes': {
                    'forward': forward_quote.get('routePlan'),
                    'backward': backward_quote.get('routePlan')
                },
                'timestamp': datetime.utcnow().isoformat()
            }
        
        if profit_percent > 0:  #   Log the opportunity if the profit percent is greater than 0
            logger.info(f"Found opportunity: {token1['symbol']}-{token2['symbol']} @ {profit_percent:.2f}%")    

        return None

    async def send_alert(self, opportunity: Dict):
        """Send alert about arbitrage opportunity via Telegram."""
        message = (
            f"🔥 Arbitrage Opportunity Found!\n\n"
            f"Tokens: {opportunity['token1_symbol']} ⟷ {opportunity['token2_symbol']}\n"
            f"Profit: {opportunity['profit_percent']:.2f}%\n"
            f"USD Value: ${opportunity['usd_value']:.2f}\n"
            f"Time: {opportunity['timestamp']}"
        )

        try:
            await self.telegram_bot.send_message(   #   Send the message to the Telegram chat
                chat_id=self.telegram_chat_id,
                text=message
            )
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")

    async def scan_pairs(self):
        """Scan all viable token pairs for arbitrage opportunities."""
        logger.info(f"Scanning {len(self.tokens)} tokens for arbitrage...")
        scanned_pairs: Set[str] = set()   #   Initialize the scanned pairs set
        
        for i, token1 in enumerate(self.tokens):    #   Iterate over the tokens
            for token2 in self.tokens[i + 1:]:  #   Iterate over the tokens starting from the next token
                pair_id = '-'.join(sorted([token1['address'], token2['address']]))  #   Get the pair ID
                if pair_id in scanned_pairs:    #   Check if the pair has already been scanned
                    continue

                scanned_pairs.add(pair_id)  #   Add the pair to the scanned pairs

                opportunity = await self.check_arbitrage(token1, token2)    #   Check for arbitrage opportunity
                if opportunity: #   Send alert if opportunity is found
                    await self.send_alert(opportunity)

                await asyncio.sleep(0.5)

    async def start(self):
        """Start the arbitrage bot."""
        if self.is_running: #   Check if the bot is already running
            return

        self.is_running = True  #   Set the running status to true
        
        try:    #   Try to initialize the bot
            await self.initialize() 
            logger.info("Starting arbitrage scanner...")

            while self.is_running:  #   Run the main loop
                await self.scan_pairs()
                await asyncio.sleep(60)
                
        except Exception as e:  #   Handle exceptions
            logger.error(f"Error in main loop: {e}")
            self.stop()
        finally:    #   Close the aiohttp session
            if self.session:
                await self.session.close()

    def stop(self): 
        """Stop the arbitrage bot."""
        self.is_running = False
        logger.info("Stopping arbitrage scanner...")

if __name__ == "__main__":
    print("Script starting...")
    try:    #   Try to load the config and initialize the bot
        config = {
            'min_profit_percent': 0.5,
            'min_liquidity': 5000,
            'telegram_token': '',
            'telegram_chat_id': ''
        }
        print("Config loaded")
        
        bot = JupiterArbitrageBot(config)   #   Initialize the bot
        print("Bot initialized")
        
        print("Starting bot...")
        asyncio.run(bot.start())    #   Start the bot
        print("Bot stopped.")
    except Exception as e:
        print(f"Error occurred: {e}")
