from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Bot
import asyncio
import logging
import aiohttp

# Set up logging
logging.basicConfig(level=logging.INFO,format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_telegram(): # Test Telegram bot
    print("Starting Telegram test...") 
    
    BOT_TOKEN = ''
    CHAT_ID = ''

    print(f"Using Bot Token: {BOT_TOKEN[:5]}...") # Only show first 5 characters
    print(f"Using Chat ID: {CHAT_ID}") 

    try:
        print("Initializing bot...")
        async with Bot(token=BOT_TOKEN) as bot: # Initialize bot
            print("Sending test message...") 
            # Send test message   
            await bot.send_message(chat_id=CHAT_ID, text='🔥 Test message from Jupiter Arbitrage Bot! If you see this, your configuration is working!')
            print("✅ Success! Check your Telegram for the test message!")
        
    except Exception as e: # Catch any errors
        print(f"❌ Error: {str(e)}")    

async def test_jupiter_api(): # Test Jupiter API
    async with aiohttp.ClientSession() as session: # Initialize aiohttp session
        # Test token list endpoint
        async with session.get('https://token.jup.ag/all') as response: # Get all tokens
            tokens = await response.json()  # Parse JSON response
            print(f"Retrieved {len(tokens)} tokens")    # Print number of tokens
        
        # Test quote endpoint with USDC and SOL
        usdc = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"   # USDC token address
        sol = "So11111111111111111111111111111111111111112"    # SOL token address
        amount = 1000000  # 1 USDC
        
        url = "https://quote-api.jup.ag/v6/quote"   # Quote endpoint
        params = {
            'inputMint': usdc,
            'outputMint': sol,
            'amount': str(amount)
        }
        
        async with session.get(url, params=params) as response: # Get quote
            quote = await response.json()   # Parse JSON response
            print("Sample quote:", quote)   # Print sample quote

if __name__ == "__main__":
    print("Starting script...")
    asyncio.run(test_telegram())    # Test Telegram bot
    print("Script finished!")
