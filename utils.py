import math
import pyotp

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees).
    Uses the Haversine formula, which requires no external C binary compilation.
    """
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')
        
    # Convert decimal degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Haversine formula
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Radius of earth in meters
    r = 6371000.0
    return c * r

def generate_totp_token(secret: str) -> str:
    """
    Generate the current Time-Based One-Time Password token.
    Rotates every 30 seconds by default.
    """
    totp = pyotp.TOTP(secret)
    return totp.now()

def verify_totp_token(secret: str, token: str) -> bool:
    """
    Verify the token against the current time window.
    Allows a drift of valid_window=1 (30s before or after) to handle
    latency and browser time drift.
    """
    if not token:
        return False
    totp = pyotp.TOTP(secret)
    # valid_window=1 permits 1 interval before and after the current token (approx. -30s to +30s drift)
    return totp.verify(token, valid_window=1)
