"""
Brewfather API Implementation
For UIFlow2.0 / MicroPython on M5Stack
"""

import requests
import binascii
import json
from brewing_software_api import BrewingSoftwareAPI, Batch, Malt, Hop


class BrewfatherAPI(BrewingSoftwareAPI):
    """Implementation of BrewingSoftwareAPI for Brewfather"""
    
    BASE_URL = "https://api.brewfather.app/v2"
    
    def __init__(self, user_id, api_key):
        """
        Initialize Brewfather API client
        
        Args:
            user_id: Brewfather user ID
            api_key: Brewfather API key
        """
        self.user_id = user_id
        self.api_key = api_key
        # Create Basic Auth header
        credentials = f"{user_id}:{api_key}"
        b64_credentials = binascii.b2a_base64(credentials.encode()).decode().strip()
        self.headers = {
            'Authorization': f'Basic {b64_credentials}',
            'Content-Type': 'application/json'
        }
    
    def get_batches(self):
        """
        Retrieve all batches from Brewfather
        
        Returns:
            List[Batch]: List of batches with batch_id and name (recipe name)
        """
        try:
            response = requests.get(f"{self.BASE_URL}/batches?status=Planning&include=_id", headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []
            
            batches_data = response.json()
            response.close()
            
            batches = []
            for batch_data in batches_data:
                recipe = batch_data.get('recipe', {})
                recipe_name = recipe.get('name', 'Unknown Recipe')
                batch = Batch(
                    batch_id=batch_data.get('_id', ''),
                    name=recipe_name
                )
                batches.append(batch)
            
            return batches
            
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_malts(self, batch_id):
        """
        Retrieve malts/grains for a specific batch from Brewfather
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Malt]: List of malts with name, EBC and amount
        """
        try:
            response = requests.get(f"{self.BASE_URL}/batches/{batch_id}?include=recipe.fermentables", headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []
            
            batch_data = response.json()
            response.close()
            
            recipe = batch_data.get('recipe', {})
            fermentables = recipe.get('fermentables', [])
            
            malts = []
            for fermentable in fermentables:
                # Filter only malts/grains (exclude sugars, extracts, etc.)
                if fermentable.get('type') in ['Grain', 'Malt']:
                    malt = Malt(
                        name=fermentable.get('name', 'Unknown Malt'),
                        ebc=fermentable.get('color', 0.0),
                        amount=fermentable.get('amount', 0.0)
                    )
                    malts.append(malt)
            
            return malts
            
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_hops(self, batch_id):
        """
        Retrieve hops for a specific batch from Brewfather
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Hop]: List of hops with name, amount, use and time
        """
        try:
            response = requests.get(f"{self.BASE_URL}/batches/{batch_id}?include=recipe.hops", headers=self.headers)
            
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []
            
            batch_data = response.json()
            response.close()
            
            recipe = batch_data.get('recipe', {})
            hops_data = recipe.get('hops', [])
            
            hops = []
            for hop_data in hops_data:
                hop = Hop(
                    name=hop_data.get('name', 'Unknown Hop'),
                    amount=hop_data.get('amount', 0.0),
                    use=hop_data.get('use', ''),
                    time=hop_data.get('time', 0)
                )
                hops.append(hop)
            
            return hops
            
        except Exception as e:
            print(f"Error: {e}")
            return []
