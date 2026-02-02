"""
Brewing Software API Interface
For UIFlow2.0 / MicroPython on M5Stack
"""


class Batch:
    """Represents a brewing batch"""
    def __init__(self, batch_id, name):
        self.batch_id = batch_id
        self.name = name
    
    def __repr__(self):
        return f"Batch(batch_id='{self.batch_id}', name='{self.name}')"


class Malt:
    """Represents a malt/grain ingredient"""
    def __init__(self, name, ebc, amount):
        self.name = name
        self.ebc = ebc
        self.amount = amount  # in kg or lbs depending on settings
    
    def __repr__(self):
        return f"Malt(name='{self.name}', ebc={self.ebc}, amount={self.amount})"


class Hop:
    """Represents a hop ingredient"""
    def __init__(self, name, amount, use, time):
        self.name = name
        self.amount = amount  # in grams
        self.use = use  # Boil, Whirlpool, Dry Hop, etc.
        self.time = time  # in minutes
    
    def __repr__(self):
        return f"Hop(name='{self.name}', amount={self.amount}, use='{self.use}', time={self.time})"


class BrewingSoftwareAPI:
    """Base class for brewing software API implementations"""
    
    def get_batches(self):
        """
        Retrieve all batches from the brewing software
        
        Returns:
            List[Batch]: List of batches with batch_id and name
        """
        raise NotImplementedError("Subclass must implement get_batches()")
    
    def get_malts(self, batch_id):
        """
        Retrieve malts/grains for a specific batch
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Malt]: List of malts with name, EBC and amount
        """
        raise NotImplementedError("Subclass must implement get_malts()")
    
    def get_hops(self, batch_id):
        """
        Retrieve hops for a specific batch
        
        Args:
            batch_id: The unique identifier of the batch
            
        Returns:
            List[Hop]: List of hops with name, amount, use and time
        """
        raise NotImplementedError("Subclass must implement get_hops()")
