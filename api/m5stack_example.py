"""
Example for M5Stack with UIFlow2.0
Shows how to use the Brewfather API
"""

import sys
sys.path.append('..')  # Access config.py from parent directory

from config import BREWFATHER_USER_ID, BREWFATHER_API_KEY
from brewfather_api import BrewfatherAPI
import network
import time


def connect_wifi(ssid, password):
    """Connect to WiFi"""
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if wlan.isconnected():
        print("Already connected")
        print("IP:", wlan.ifconfig()[0])
        return True
    
    print(f"Connecting to {ssid}...")
    wlan.connect(ssid, password)
    
    # Wait for connection (max 10 seconds)
    timeout = 10
    while not wlan.isconnected() and timeout > 0:
        time.sleep(1)
        timeout -= 1
    
    if wlan.isconnected():
        print("Connected!")
        print("IP:", wlan.ifconfig()[0])
        return True
    else:
        print("Connection failed")
        return False


def main():
    """Main function"""
    
    # TODO: Replace with your WiFi credentials
    WIFI_SSID = "YOUR_WIFI_SSID"
    WIFI_PASSWORD = "YOUR_WIFI_PASSWORD"
    
    if not connect_wifi(WIFI_SSID, WIFI_PASSWORD):
        print("Cannot continue without WiFi")
        return
    
    # Initialize Brewfather API
    print("\nInitializing API...")
    api = BrewfatherAPI(BREWFATHER_USER_ID, BREWFATHER_API_KEY)
    
    # Get batches
    print("Fetching batches...")
    batches = api.get_batches()
    
    if not batches:
        print("No batches found or error occurred")
        return
    
    print(f"\nFound {len(batches)} batches:\n")
    
    # Display all batches
    for i, batch in enumerate(batches, 1):
        print(f"{i}. {batch.name}")
    
    # Get details for first batch
    if batches:
        first_batch = batches[0]
        print("\n" + "="*50)
        print(f"Details: {first_batch.name}")
        print("="*50 + "\n")
        
        # Get malts
        print("Malts/Grains:")
        malts = api.get_malts(first_batch.batch_id)
        
        if malts:
            total = 0
            for malt in malts:
                print(f"  {malt.name}")
                print(f"  {malt.amount:.3f} kg - {malt.ebc} EBC")
                total += malt.amount
            print(f"\n  Total: {total:.3f} kg")
        else:
            print("  No malts")
        
        # Get hops
        print("\nHops:")
        hops = api.get_hops(first_batch.batch_id)
        
        if hops:
            for hop in hops:
                print(f"  {hop.name}")
                print(f"  {hop.amount} g")
                print(f"  {hop.use} - {hop.time} min")
        else:
            print("  No hops")
        
        print("\n" + "="*50 + "\n")


# Run the example
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {e}")
        import sys
        sys.print_exception(e)
