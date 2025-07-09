# File: check_keys.py (ВЕРСИЯ С ХАРДКОДОМ)
import os
import asyncio
import ccxt.async_support as ccxt
# from dotenv import load_dotenv # Больше не нужно

async def main():
    # load_dotenv() # Больше не нужно
    
    # --- ВРЕМЕННО ВСТАВЛЯЕМ КЛЮЧИ ПРЯМО СЮДА ---
    api_key = "Xyo4o0isLLDU1vaRlN"
    secret = "L4BnWcl26eeeWYT3keMiKLtnFwmKm0tKQoJp"
    # ---------------------------------------------

    print(f"--- Checking Keys (Hardcoded) ---")
    print(f"API Key used: {api_key}")
    print("-" * 20)

    exchange = ccxt.bybit({
        'apiKey': api_key,
        'secret': secret,
    })
    exchange.set_sandbox_mode(True)

    try:
        print("Attempting to fetch balance...")
        balance = await exchange.fetch_balance()
        print("\nSUCCESS! Connection is working.")
        print(f"Available USDT Balance: {balance.get('USDT', {}).get('free', 0.0)}")
    except ccxt.AuthenticationError as e:
        print(f"\nERROR: Authentication failed. Bybit says: {e}")
        print("This confirms the issue is with the keys themselves or their permissions on Bybit's side.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())