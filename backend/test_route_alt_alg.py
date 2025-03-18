import os
import sys
import pytest
import pandas as pd
import networkx as nx
from unittest.mock import patch, MagicMock
import time

# Patch geocoder BEFORE importing route_alt_alg
# This prevents the real geocoder from being used during import
with patch('geopy.geocoders.Nominatim') as mock_geocoder_class:
    # Configure the mock geocoder
    mock_geocoder = MagicMock()
    mock_geocoder_class.return_value = mock_geocoder
    
    # Setup mock locations
    mock_location1 = MagicMock()
    mock_location1.latitude = 37.7773
    mock_location1.longitude = -122.4950
    
    mock_location2 = MagicMock()
    mock_location2.latitude = 37.7884
    mock_location2.longitude = -122.4100
    
    # Configure geocode method to return different locations based on address
    def mock_geocode(address):
        if "35th ave" in address.lower():
            return mock_location1
        elif "mason st" in address.lower():
            return mock_location2
        return None
    
    mock_geocoder.geocode = mock_geocode
    
    # Now import route_alt_alg after the mock is in place
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import route_alt_alg

class TestRouteAltAlg:
    @pytest.fixture
    def setup_test_data(self):
        """Setup test data for route algorithm tests"""
        # Create a small test graph
        G = nx.DiGraph()
        
        # Add nodes (stops)
        stops = {
            "BALB_1": (37.7773, -122.4950),
            "BALB": (37.7762, -122.4947),
            "GLEN": (37.7331, -122.4338),
            "24TH": (37.7524, -122.4186),
            "16TH": (37.7651, -122.4195),
            "CIVC": (37.7793, -122.4138),
            "POWL": (37.7844, -122.4079),
            "POWL_7": (37.7884, -122.4100)
        }
        
        for stop_id, (lat, lon) in stops.items():
            G.add_node(stop_id, pos=(lat, lon))
        
        # Add transit edges
        G.add_edge("BALB", "GLEN", weight=0.01, type="transit", route_id="RED")
        G.add_edge("GLEN", "24TH", weight=0.01, type="transit", route_id="RED")
        G.add_edge("24TH", "16TH", weight=0.01, type="transit", route_id="RED")
        G.add_edge("16TH", "CIVC", weight=0.01, type="transit", route_id="RED")
        G.add_edge("CIVC", "POWL", weight=0.01, type="transit", route_id="RED")
        
        # Add walking edges
        G.add_edge("BALB_1", "BALB", weight=0.005, type="walking")
        G.add_edge("BALB", "BALB_1", weight=0.005, type="walking")
        G.add_edge("POWL", "POWL_7", weight=0.005, type="walking")
        G.add_edge("POWL_7", "POWL", weight=0.005, type="walking")
        
        # Setup mock stops dataframe
        stops_data = []
        for stop_id, (lat, lon) in stops.items():
            name = stop_id.split('_')[0]
            stops_data.append({
                'stop_id': stop_id,
                'stop_name': f"Test Stop {name}",
                'stop_lat': str(lat),
                'stop_lon': str(lon)
            })
        
        stops_df = pd.DataFrame(stops_data)
        
        # Setup landmarks and distances
        landmarks = ["BALB", "POWL"]
        landmark_distances = {
            "BALB": {
                "BALB_1": 0.005, "BALB": 0.0, "GLEN": 0.01, "24TH": 0.02, 
                "16TH": 0.03, "CIVC": 0.04, "POWL": 0.05, "POWL_7": 0.055
            },
            "POWL": {
                "BALB_1": 0.055, "BALB": 0.05, "GLEN": 0.04, "24TH": 0.03, 
                "16TH": 0.02, "CIVC": 0.01, "POWL": 0.0, "POWL_7": 0.005
            }
        }
        
        return {
            "G": G,
            "stops": stops,
            "stops_df": stops_df,
            "landmarks": landmarks,
            "landmark_distances": landmark_distances
        }
    
    def test_find_nearest_stop(self, setup_test_data):
        """Test finding nearest stop to an address"""
        # Setup
        test_data = setup_test_data
        route_alt_alg.stops = test_data["stops"]
        route_alt_alg.stops_df = test_data["stops_df"]
        
        # Test
        result = route_alt_alg.find_nearest_stop("618 35th ave, San Francisco")
        
        # Assert
        assert result == "BALB_1"
    
    def test_alt_algorithm(self, setup_test_data):
        """Test ALT algorithm for finding paths between stops"""
        # Setup
        test_data = setup_test_data
        # Save original values
        orig_g = route_alt_alg.G
        orig_landmarks = route_alt_alg.landmarks
        orig_landmark_distances = route_alt_alg.landmark_distances
        
        # Replace with test values
        route_alt_alg.G = test_data["G"]
        route_alt_alg.landmarks = test_data["landmarks"]
        route_alt_alg.landmark_distances = test_data["landmark_distances"]
        
        try:
            # Test
            path, edge_types = route_alt_alg.alt_algorithm(test_data["G"], "BALB_1", "POWL_7")
            
            # Assert
            assert path is not None
            assert edge_types is not None
            assert len(path) > 0
            assert path[0] == "BALB_1"
            assert path[-1] == "POWL_7"
            assert "walking" in edge_types
            assert "transit" in edge_types
        finally:
            # Restore original values
            route_alt_alg.G = orig_g
            route_alt_alg.landmarks = orig_landmarks
            route_alt_alg.landmark_distances = orig_landmark_distances
    
    def test_end_to_end_route_finding(self, setup_test_data):
        """Test end-to-end route finding from one address to another"""
        # Setup
        test_data = setup_test_data
        
        # Save original values
        orig_stops = route_alt_alg.stops
        orig_stops_df = route_alt_alg.stops_df
        orig_g = route_alt_alg.G
        
        # Replace with test values
        route_alt_alg.stops = test_data["stops"]
        route_alt_alg.stops_df = test_data["stops_df"]
        route_alt_alg.G = test_data["G"]
        
        try:
            # Test
            start_stop = route_alt_alg.find_nearest_stop("618 35th ave, San Francisco")
            end_stop = route_alt_alg.find_nearest_stop("520 mason st., San Francisco")
            
            # Assert
            assert start_stop == "BALB_1"
            assert end_stop == "POWL_7"
            
            # Use our test graph to avoid dependency on actual graph data
            path, edge_types = route_alt_alg.alt_algorithm(test_data["G"], start_stop, end_stop)
            
            # Assert path exists
            assert path is not None
            assert len(path) > 0
            assert path[0] == start_stop
            assert path[-1] == end_stop
        finally:
            # Restore original values
            route_alt_alg.stops = orig_stops
            route_alt_alg.stops_df = orig_stops_df
            route_alt_alg.G = orig_g

# Helper function to run a test with real addresses (for manual testing only)
def test_with_real_data():
    """Run a test with real addresses and actual data"""
    try:
        # Define test addresses
        start_address = "618 35th ave, San Francisco"
        end_address = "520 mason st., San Francisco"
        
        # Find nearest stops
        start_stop = route_alt_alg.find_nearest_stop(start_address)
        end_stop = route_alt_alg.find_nearest_stop(end_address)
        
        # Find path
        path, edge_types = route_alt_alg.alt_algorithm(route_alt_alg.G, start_stop, end_stop)
        
        # Print results for verification
        print("\n----- TEST RESULTS: Real Addresses -----")
        print(f"Start: {start_address} → Stop ID: {start_stop}")
        print(f"End: {end_address} → Stop ID: {end_stop}")
        print(f"Path length: {len(path)} stops")
        print(f"Transit segments: {edge_types.count('transit')}")
        print(f"Walking segments: {edge_types.count('walking')}")
        
        # Print full path
        print("\nFull path:")
        for i, stop_id in enumerate(path):
            stop_name = "Unknown"
            for idx, row in route_alt_alg.stops_df.iterrows():
                if row['stop_id'] == stop_id:
                    stop_name = row['stop_name']
                    break
                    
            print(f"{i+1}. {stop_name} ({stop_id})")
            
            # Show edge type if not at the end
            if i < len(path) - 1:
                edge_type = route_alt_alg.G[path[i]][path[i+1]].get('type', 'unknown')
                print(f"   → [{edge_type.upper()}]")
        
        print("\n✅ Test completed successfully!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    # Run pytest tests by default
    result = pytest.main(["-v", __file__])
    
    # Uncomment to run the manual test with real data 
    # (be aware this uses actual geocoding services)
    # if result == 0:
    #     print("\nRunning test with real data...")
    #     test_with_real_data()