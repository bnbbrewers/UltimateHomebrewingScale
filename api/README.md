# Brewing Software API for M5Stack UIFlow2.0

A MicroPython interface for connecting M5Stack devices to brewing software platforms like Brewfather.

**For UIFlow2.0 only** - No external dependencies required!

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [API Methods](#api-methods)
- [Complete Example](#complete-example)
- [Implementing Other Brewing Software](#implementing-other-brewing-software)
- [Troubleshooting](#troubleshooting)

---

## Overview

This module provides a simple, extensible interface for brewing software APIs. It allows your M5Stack device to:
- Retrieve brewing recipes
- List ingredients (malts, hops)
- Guide weighing processes
- Automate brewing tasks

### Why an Interface?

The `BrewingSoftwareAPI` base class provides a common interface for different brewing software platforms. This means:
- **Consistent API**: Same methods work across different platforms
- **Easy switching**: Change from Brewfather to Beersmith without rewriting code
- **Extensible**: Add new platforms by implementing the interface

### Current Implementation

✅ **Brewfather** - Full support with `BrewfatherAPI`

---

## Architecture

### Project Structure

```
UltimateHomebrewingScale/
├── config.py              # Configuration (create from config.py.example)
└── api/
    ├── brewing_software_api.py  # Base interface
    ├── brewfather_api.py        # Brewfather implementation
    ├── m5stack_example.py       # Complete example
    └── README.md                # This file
```

### Class Hierarchy

```
BrewingSoftwareAPI (Base Interface)
    │
    ├── BrewfatherAPI (Implemented)
    ├── ... (To implement)
```

### Data Models

**Batch**: Represents a brewing batch
```python
class Batch:
    batch_id: str  # Unique identifier
    name: str      # Recipe name
```

**Malt**: Represents a malt/grain ingredient
```python
class Malt:
    name: str      # Malt name
    ebc: float     # Color in EBC
    amount: float  # Quantity in kg
```

**Hop**: Represents a hop ingredient
```python
class Hop:
    name: str      # Hop name
    amount: float  # Quantity in g
    use: str       # Usage (Boil, Dry Hop, etc.)
    time: int      # Time in minutes
```

---

## Quick Start

### 1. Configuration

Create `config.py` at the project root:

```python
# config.py
BREWFATHER_USER_ID = "your_user_id"
BREWFATHER_API_KEY = "your_api_key"
```

Get credentials: https://web.brewfather.app/tabs/settings

### 2. Copy to M5Stack

Copy these files to your M5Stack:
```
/ (M5Stack root)
├── config.py
└── api/
    ├── brewing_software_api.py
    └── brewfather_api.py
```

---

## API Methods

### `get_batches()`

Retrieve all batches from the brewing software.

**Returns**: List of `Batch` objects

**Example**:
```python
batches = api.get_batches()
for batch in batches:
    print(f"{batch.name} (ID: {batch.batch_id})")
```

### `get_malts(batch_id)`

Retrieve malts/grains for a specific batch.

**Parameters**:
- `batch_id` (str): The batch unique identifier

**Returns**: List of `Malt` objects

**Example**:
```python
malts = api.get_malts(batch_id)
total = 0
for malt in malts:
    print(f"  {malt.name}: {malt.amount:.3f} kg - {malt.ebc} EBC")
    total += malt.amount
print(f"Total: {total:.3f} kg")
```

### `get_hops(batch_id)`

Retrieve hops for a specific batch.

**Parameters**:
- `batch_id` (str): The batch unique identifier

**Returns**: List of `Hop` objects

**Example**:
```python
hops = api.get_hops(batch_id)
for hop in hops:
    print(f"  {hop.name}: {hop.amount} g")
    print(f"  {hop.use} - {hop.time} min")
```

---

## Complete Example

See `m5stack_example.py` for a full working example including:
- WiFi connection
- Batch retrieval
- Ingredient display
- Error handling

Quick run:
```python
from api import m5stack_example
m5stack_example.main()
```

---

## Implementing Other Brewing Software

Want to add support for another brewing software platform? Follow these steps:

### 1. Create a New Class

Create a new file (e.g., `beersmith_api.py`) that inherits from `BrewingSoftwareAPI`:

```python
# beersmith_api.py
from brewing_software_api import BrewingSoftwareAPI, Batch, Malt, Hop
import requests
import binascii

class BeersmithAPI(BrewingSoftwareAPI):
    """Implementation for Beersmith Cloud"""
    
    BASE_URL = "https://api.beersmith.com/v1"
    
    def __init__(self, api_key):
        """
        Initialize Beersmith API client
        
        Args:
            api_key: Your Beersmith API key
        """
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
```

### 2. Implement Required Methods

You **must** implement these three methods:

#### `get_batches()`

```python
    def get_batches(self):
        """Retrieve all batches"""
        try:
            response = urequests.get(
                f"{self.BASE_URL}/recipes",
                headers=self.headers
            )
            
            if response.status_code != 200:
                response.close()
                return []
            
            data = response.json()
            response.close()
            
            batches = []
            for recipe in data:
                batch = Batch(
                    batch_id=recipe['id'],
                    label=recipe['name']
                )
                batches.append(batch)
            
            return batches
            
        except Exception as e:
            print(f"Error: {e}")
            return []
```

#### `get_malts(batch_id)`

```python
    def get_malts(self, batch_id):
        """Retrieve malts for a batch"""
        try:
            response = urequests.get(
                f"{self.BASE_URL}/recipes/{batch_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                response.close()
                return []
            
            data = response.json()
            response.close()
            
            malts = []
            for grain in data.get('grains', []):
                malt = Malt(
                    name=grain['name'],
                    ebc=grain['color'],
                    amount=grain['amount']
                )
                malts.append(malt)
            
            return malts
            
        except Exception as e:
            print(f"Error: {e}")
            return []
```

#### `get_hops(batch_id)`

```python
    def get_hops(self, batch_id):
        """Retrieve hops for a batch"""
        try:
            response = urequests.get(
                f"{self.BASE_URL}/recipes/{batch_id}",
                headers=self.headers
            )
            
            if response.status_code != 200:
                response.close()
                return []
            
            data = response.json()
            response.close()
            
            hops = []
            for hop_data in data.get('hops', []):
                hop = Hop(
                    name=hop_data['name'],
                    amount=hop_data['amount'],
                    use=hop_data['use'],
                    time=hop_data['time']
                )
                hops.append(hop)
            
            return hops
            
        except Exception as e:
            print(f"Error: {e}")
            return []
```

### 3. Usage

Once implemented, use it exactly like Brewfather:

```python
from api.beersmith_api import BeersmithAPI

api = BeersmithAPI(api_key="your_api_key")
batches = api.get_batches()
malts = api.get_malts(batches[0].batch_id)
```

### 4. Tips for Implementation

**Authentication**:
- Most APIs use Bearer tokens or Basic Auth
- Store credentials in `config.py`
- Use `ubinascii.b2a_base64()` for Base64 encoding

**HTTP Requests**:
- Always close responses: `response.close()`
- Check `response.status_code` before parsing
- Handle exceptions gracefully

**Data Mapping**:
- Map API response fields to `Batch` and `Malt` objects
- Use `.get()` with defaults for optional fields
- Filter ingredients by type if needed

**Error Handling**:
- Return empty lists on errors
- Print error messages for debugging
- Don't crash on network failures

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `ImportError: urequests` | Use UIFlow2.0 (not UIFlow1) |
| HTTP 401 Unauthorized | Check credentials in `config.py` |
| Connection timeout | Verify WiFi and internet connection |
| Empty response | Check API endpoint and data format |
| JSON parsing error | Verify API returns valid JSON |

### Debug Mode

Add debug prints to see raw API responses:

```python
response = urequests.get(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
```

---

## Libraries Used

All native to UIFlow2.0:
- `urequests` - HTTP requests
- `ubinascii` - Base64 encoding
- `json` - JSON parsing
- `network` - WiFi connectivity

---

## Resources

- [Brewfather API Documentation](https://docs.brewfather.app/api)
- [UIFlow2.0 Documentation](https://docs.m5stack.com/en/quick_start/m5dial/uiflow)
- [Example Code](m5stack_example.py)

---

## Contributing

To add support for a new brewing software:
1. Implement the `BrewingSoftwareAPI` interface
2. Follow the naming convention: `{platform}_api.py`
3. Test on actual M5Stack hardware
4. Update this README with the new platform

---

## License

See the main project LICENSE file.
