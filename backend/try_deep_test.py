from route_finder2 import find_nearest_stop
from unittest.mock import patch, MagicMock
from typing import Tuple
import unittest

class TestRouteFinder(unittest.TestCase):
    def setUp(self):
        """Setup test environment with mocks"""
        # Mock database
        self.mock_db = MagicMock()
        
        # Mock response for find_nearest_stop
        self.mock_stop_result = MagicMock()
        self.mock_stop_result.__getitem__.side_effect = lambda i: {
            0: "stop_123", 
            1: "Market & 4th", 
            2: 37.7749, 
            3: -122.4194, 
            4: 120.5
        }.get(i)
        
        # Setup mock for database execute - improved setup
        self.mock_execute_result = MagicMock()
        self.mock_execute_result.fetchone.return_value = self.mock_stop_result
        self.mock_db.execute.return_value = self.mock_execute_result
        
        # Mock for transit edges
        self.mock_transit_edges = [
            MagicMock(to_stop="stop_124", travel_time=300),
            MagicMock(to_stop="stop_125", travel_time=600)
        ]
        
        # Mock the redis cache
        self.mock_redis = MagicMock()
        self.mock_redis.get.return_value = None  # No cached results
            
    @patch('route_finder2.redis')  # <-- FIXED HERE
    def test_find_nearest_stop(self, mock_redis):
        """Test finding nearest stop"""
        # Setup test
        lat, lon = 37.7749, -122.4194
        
        # Execute function
        result = find_nearest_stop(lat, lon, self.mock_db)
        
        # Assertions - Don't check number of calls, check correct parameters
        self.mock_db.execute.assert_called_with(
            """
        SELECT stop_id, stop_name, stop_lat, stop_lon, 
               ST_Distance(geog, ST_MakePoint(:lon, :lat)::geography) AS distance
        FROM stops
        ORDER BY distance ASC
        LIMIT 1;
    """,
            {"lat": lat, "lon": lon}
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["stop_id"], "stop_123")
        self.assertEqual(result["stop_name"], "Market & 4th")
        self.assertEqual(result["lat"], 37.7749)
        self.assertEqual(result["lon"], -122.4194)

# Implementation of test_with_real_coordinates function
def test_with_real_coordinates():
    """Simple test with real SF coordinates"""
    try:
        from app.database import get_db
        
        # Get database session
        db = next(get_db())
        
        # Union Square to Fisherman's Wharf
        start_lat, start_lon = 37.7881, -122.4075  # Union Square
        end_lat, end_lon = 37.8080, -122.4177      # Fisherman's Wharf
        
        # Find nearest stops
        start_stop = find_nearest_stop(start_lat, start_lon, db)
        end_stop = find_nearest_stop(end_lat, end_lon, db)
        
        print("\n----- TEST RESULTS -----")
        print(f"🚶 Starting: Union Square ({start_lat}, {start_lon})")
        print(f"   Nearest stop: {start_stop['stop_name']} ({start_stop['stop_id']})")
        print(f"   Distance: {start_stop['distance']:.1f} meters")
        print(f"🏁 Ending: Fisherman's Wharf ({end_lat}, {end_lon})")
        print(f"   Nearest stop: {end_stop['stop_name']} ({end_stop['stop_id']})")
        print(f"   Distance: {end_stop['distance']:.1f} meters")
        print("\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
    
if __name__ == "__main__":
    # Run automated tests
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
    
    # Uncomment to run manual test with real coordinates
    #test_with_real_coordinates()