"""
Brewfather API Implementation
For UIFlow2.0 / MicroPython on M5Stack
"""

import binascii
from .brewing_software_api import ApiBase, Batch, Malt, Hop


class BrewfatherAPI(ApiBase):
    """Implementation of BrewingSoftwareAPI for Brewfather"""

    BASE_URL = "https://api.brewfather.app/v2"

    def __init__(self):
        """
        Initialize Brewfather API client.
        Credentials are read from config.BREWFATHER_USER_ID / BREWFATHER_API_KEY.
        """
        try:
            import config
            user_id = getattr(config, 'BREWFATHER_USER_ID', '')
            api_key  = getattr(config, 'BREWFATHER_API_KEY',  '')
        except ImportError:
            user_id = ''
            api_key  = ''

        self.user_id = user_id
        self.api_key  = api_key
        credentials = f"{user_id}:{api_key}"
        b64 = binascii.b2a_base64(credentials.encode()).decode().strip()
        self.headers = {
            'Authorization': f'Basic {b64}',
            'Content-Type': 'application/json',
        }

    def get_batches(self):
        """
        Retrieve all batches from Brewfather

        Returns:
            List[Batch]: batches with batch_id and recipe name
        """
        try:
            response = self._get(
                f"{self.BASE_URL}/batches?status=Brewing&include=_id",
                self.headers,
            )
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []

            batches_data = response.json()
            response.close()

            batches = []
            for batch_data in batches_data:
                recipe = batch_data.get('recipe', {})
                batch = Batch(
                    batch_id=batch_data.get('_id', ''),
                    name=recipe.get('name', 'Unknown Recipe'),
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
            List[Malt]: malts with name, EBC and amount
        """
        try:
            response = self._get(
                f"{self.BASE_URL}/batches/{batch_id}?include=recipe.fermentables",
                self.headers,
            )
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []

            batch_data = response.json()
            response.close()

            fermentables = batch_data.get('recipe', {}).get('fermentables', [])
            malts = []
            for f in fermentables:
                if f.get('type') in ['Grain', 'Malt']:
                    malts.append(Malt(
                        name=f.get('name', 'Unknown Malt'),
                        ebc=f.get('color', 0.0),
                        amount=f.get('amount', 0.0),
                    ))
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
            List[Hop]: hops with name, amount, use and time
        """
        try:
            response = self._get(
                f"{self.BASE_URL}/batches/{batch_id}?include=recipe.hops",
                self.headers,
            )
            if response.status_code != 200:
                print(f"Error: HTTP {response.status_code}")
                response.close()
                return []

            batch_data = response.json()
            response.close()

            hops_data = batch_data.get('recipe', {}).get('hops', [])
            hops = []
            for h in hops_data:
                hops.append(Hop(
                    name=h.get('name', 'Unknown Hop'),
                    amount=h.get('amount', 0.0),
                    use=h.get('use', ''),
                    time=h.get('time', 0),
                ))
            return hops

        except Exception as e:
            print(f"Error: {e}")
            return []
