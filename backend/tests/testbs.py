import pytest
import pandas as pd
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime, timedelta
import os
import sys
import math

# Adjust the path to import your BusService class correctly
# This assumes tests/ is at the same level as app/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.services.bus_service import BusService # Adjust the import path if necessary

# --- Sample Data ---

# Sample GTFS data as Pandas DataFrames
SAMPLE_ROUTES_DF = pd.DataFrame({
    'route_id': ['1', '22'],
    'route_short_name': ['1', '22'],
    'route_long_name': ['1-California', '22-Fillmore']
})

SAMPLE_TRIPS_DF = pd.DataFrame({
    'trip_id': ['T1_In', 'T1_Out', 'T22_In', 'T22_Out'],
    'route_id': ['1', '1', '22', '22'],
    'service_id': ['Svc1', 'Svc1', 'Svc1', 'Svc1'],
    'direction_id': ['1', '0', '1', '0'], # 1=Inbound, 0=Outbound assumed
    'trip_headsign': ['Downtown', 'Ocean Beach', 'Mission Bay', 'Marina Blvd']
})

SAMPLE_STOPS_DF = pd.DataFrame({
    'stop_id': ['123', '456', '789', '999'],
    'stop_name': ['Stop A', 'Stop B', 'Stop C - Far', 'Stop D - Future'],
    'stop_lat': [37.7750, 37.7755, 37.8000, 37.7751], # Stop C is far away
    'stop_lon': [-122.4190, -122.4195, -122.4500, -122.4191]
})

# Sample stop_times for Stop A ('123')
# Add times spanning across midnight (e.g., 24:15:00) and within/outside the 2-hour window
NOW = datetime.now()
TIME_FORMAT = "%H:%M:%S"
IN_1_HOUR = (NOW + timedelta(hours=1)).strftime(TIME_FORMAT)
IN_3_HOURS = (NOW + timedelta(hours=3)).strftime(TIME_FORMAT) # Outside 2-hour window
YESTERDAY_TIME = (NOW - timedelta(hours=1)).strftime(TIME_FORMAT)
NEXT_DAY_TIME_STR = f"{int(NOW.strftime('%H'))+24}:{NOW.strftime('%M')}:{NOW.strftime('%S')}" # e.g., 25:30:00


SAMPLE_STOP_TIMES_DF = pd.DataFrame({
    'trip_id': ['T1_In', 'T1_Out', 'T22_In', 'T22_Out', 'T1_In_Late', 'T1_Out_Early', 'T1_In_NextDay'],
    'stop_id': ['123', '123', '123', '456', '123', '123', '123'], # Stop 456 only used for T22_Out
    'arrival_time': [IN_1_HOUR, IN_1_HOUR, IN_1_HOUR, '10:15:00', IN_3_HOURS, YESTERDAY_TIME, NEXT_DAY_TIME_STR],
    'departure_time': [IN_1_HOUR, IN_1_HOUR, IN_1_HOUR, '10:15:30', IN_3_HOURS, YESTERDAY_TIME, NEXT_DAY_TIME_STR],
    'stop_sequence': ['1', '1', '1', '5', '1', '1','1']
})

SAMPLE_CALENDAR_DF = pd.DataFrame({
    'service_id': ['Svc1'],
    'monday': [1], 'tuesday': [1], 'wednesday': [1], 'thursday': [1],
    'friday': [1], 'saturday': [1], 'sunday': [1],
    'start_date': [(NOW - timedelta(days=30)).strftime("%Y%m%d")],
    'end_date': [(NOW + timedelta(days=30)).strftime("%Y%m%d")]
})

# Sample 511 API XML Response (Vehicle Monitoring)
SAMPLE_VEHICLE_XML = """
<Siri version="1.0" xmlns="http://www.siri.org.uk/siri">
  <ServiceDelivery>
    <VehicleMonitoringDelivery>
      <VehicleActivity>
        <MonitoredVehicleJourney>
          <LineRef>22</LineRef>
          <VehicleLocation>
            <Latitude>37.776</Latitude>
            <Longitude>-122.420</Longitude>
          </VehicleLocation>
          <MonitoredCall>
            <StopPointName>Current Stop Name</StopPointName>
            <ExpectedArrivalTime>2023-10-27T10:30:00Z</ExpectedArrivalTime>
          </MonitoredCall>
        </MonitoredVehicleJourney>
      </VehicleActivity>
      <VehicleActivity>
        <MonitoredVehicleJourney>
          <LineRef>1</LineRef>
           <VehicleLocation>
            <Latitude>37.774</Latitude>
            <Longitude>-122.418</Longitude>
          </VehicleLocation>
          <MonitoredCall>
            <StopPointName>Another Stop</StopPointName>
            <ExpectedArrivalTime>2023-10-27T10:35:00Z</ExpectedArrivalTime>
          </MonitoredCall>
        </MonitoredVehicleJourney>
      </VehicleActivity>
    </VehicleMonitoringDelivery>
  </ServiceDelivery>
</Siri>
"""

# Sample 511 API JSON Response (Stop Monitoring - Real-time)
REAL_TIME_ARRIVAL_ISO = (NOW + timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M:%SZ')
AIMED_ARRIVAL_ISO = (NOW + timedelta(minutes=11)).strftime('%Y-%m-%dT%H:%M:%SZ') # 1 min late
REAL_TIME_ARRIVAL_ISO_EARLY = (NOW + timedelta(minutes=15)).strftime('%Y-%m-%dT%H:%M:%SZ')
AIMED_ARRIVAL_ISO_EARLY = (NOW + timedelta(minutes=17)).strftime('%Y-%m-%dT%H:%M:%SZ') # 2 min early

SAMPLE_STOP_MONITORING_JSON = {
  "ServiceDelivery": {
    "StopMonitoringDelivery": {
      "MonitoredStopVisit": [
        {
          "MonitoredVehicleJourney": {
            "LineRef": "SF:1", # Real-time data often has agency prefix
            "DirectionRef": "1", # Inbound
            "DestinationName": ["Downtown"],
            "MonitoredCall": {
              "ExpectedArrivalTime": REAL_TIME_ARRIVAL_ISO,
              "AimedArrivalTime": AIMED_ARRIVAL_ISO
            }
          }
        },
        {
          "MonitoredVehicleJourney": {
            "LineRef": "SF:1",
             "DirectionRef": "0", # Outbound
            "DestinationName": ["Ocean Beach"],
            "MonitoredCall": {
              "ExpectedArrivalTime": REAL_TIME_ARRIVAL_ISO_EARLY,
              "AimedArrivalTime": AIMED_ARRIVAL_ISO_EARLY
            }
          }
        },
         { # Arrival outside 2 hour window
          "MonitoredVehicleJourney": {
            "LineRef": "SF:22",
            "DirectionRef": "1",
            "DestinationName": ["Mission Bay"],
            "MonitoredCall": {
              "ExpectedArrivalTime": (NOW + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ'),
              "AimedArrivalTime": (NOW + timedelta(hours=3)).strftime('%Y-%m-%dT%H:%M:%SZ')
            }
          }
        }
      ]
    }
  }
}


# --- Pytest Fixture ---

@pytest.fixture
def mock_dependencies(mocker):
    """Mocks dependencies like file reads, env vars, and API calls."""
    # Mock environment variables
    mocker.patch('os.getenv', side_effect=lambda key, default=None: {
        "API_KEY": "TEST_API_KEY",
        "AGENCY_ID": "SFMTA" # Keep it simple for tests
    }.get(key, default))

    # Mock os.makedirs to do nothing
    mocker.patch('os.makedirs')

    # Mock pd.read_csv to return our sample dataframes
    def mock_read_csv(filepath, dtype):
        if 'routes.txt' in filepath:
            return SAMPLE_ROUTES_DF.copy()
        elif 'trips.txt' in filepath:
            return SAMPLE_TRIPS_DF.copy()
        elif 'stops.txt' in filepath:
            # Note: _load_stops uses open(), we'll mock that separately if needed
             # For __init__, let's return the DF
            return SAMPLE_STOPS_DF.copy()
        elif 'stop_times.txt' in filepath:
            return SAMPLE_STOP_TIMES_DF.copy()
        elif 'calendar.txt' in filepath:
            return SAMPLE_CALENDAR_DF.copy()
        else:
            raise FileNotFoundError(f"Unexpected file path in mock_read_csv: {filepath}")
    mocker.patch('pandas.read_csv', side_effect=mock_read_csv)

    # Mock requests.get
    mock_response_vehicle = MagicMock()
    mock_response_vehicle.status_code = 200
    mock_response_vehicle.text = SAMPLE_VEHICLE_XML

    mock_response_stop = MagicMock()
    mock_response_stop.status_code = 200
    mock_response_stop.content = json.dumps(SAMPLE_STOP_MONITORING_JSON).encode('utf-8-sig')
    mock_response_stop.json.return_value = SAMPLE_STOP_MONITORING_JSON # If .json() is used
    # Add decode method to mock response content
    mock_response_stop.content.decode.return_value = json.dumps(SAMPLE_STOP_MONITORING_JSON)


    mock_get = mocker.patch('requests.get')
    # Default mock to return stop monitoring, adjust per test if needed
    mock_get.return_value = mock_response_stop

    # Mock file open for _load_stops (alternative to mocking read_csv for stops)
    stops_csv_content = "stop_id,stop_name,stop_lat,stop_lon\n" + \
                        "123,Stop A,37.7750,-122.4190\n" + \
                        "456,Stop B,37.7755,-122.4195\n" + \
                        "789,Stop C - Far,37.8000,-122.4500\n" + \
                        "999,Stop D - Future,37.7751,-122.4191\n"
    mocker.patch('builtins.open', mock_open(read_data=stops_csv_content))
    mocker.patch('os.path.exists', return_value=True) # Assume stops.txt exists


    return {
        'mock_get': mock_get,
        'mock_response_vehicle': mock_response_vehicle,
        'mock_response_stop': mock_response_stop
    }


@pytest.fixture
def bus_service_instance(mock_dependencies):
    """Provides a BusService instance with mocked dependencies."""
    # The mocks in mock_dependencies are active here
    service = BusService()
    # Reset cache state if necessary for tests (though fixture usually handles this)
    service.stops_cache = None
    return service

# --- Test Functions ---

def test_initialization(bus_service_instance):
    """Test if BusService initializes correctly and loads GTFS data."""
    service = bus_service_instance
    assert service.api_key == "TEST_API_KEY"
    assert service.agency_ids == ["SFMTA"]
    assert 'routes' in service.gtfs_data
    assert 'stops' in service.gtfs_data
    assert not service.gtfs_data['routes'].empty
    assert not service.gtfs_data['stops'].empty
    # Add more assertions for other GTFS data if needed

@pytest.mark.skip(reason="Needs specific mock setup for VehicleMonitoring URL")
def test_get_live_bus_positions_success(bus_service_instance, mock_dependencies):
    """Test fetching live bus positions successfully."""
    service = bus_service_instance
    mock_get = mock_dependencies['mock_get']
    mock_response_vehicle = mock_dependencies['mock_response_vehicle']

    # Configure mock_get specifically for this test's URL
    mock_get.side_effect = lambda url, **kwargs: mock_response_vehicle if 'VehicleMonitoring' in url else MagicMock(status_code=404)


    bus_number_to_find = "22"
    positions = service.get_live_bus_positions(bus_number_to_find, "SFMTA")

    assert isinstance(positions, list)
    assert len(positions) == 1 # Only one vehicle matched '22' in sample XML
    assert positions[0]['bus_number'] == bus_number_to_find
    assert positions[0]['latitude'] == "37.776"
    mock_get.assert_called_once_with(f"{service.base_url}/VehicleMonitoring?api_key=TEST_API_KEY&agency=SFMTA")


def test_get_live_bus_positions_failure(bus_service_instance, mock_dependencies):
    """Test fetching live bus positions when API fails."""
    service = bus_service_instance
    mock_get = mock_dependencies['mock_get']

    # Configure mock_get for failure
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_get.side_effect = lambda url, **kwargs: mock_response_fail if 'VehicleMonitoring' in url else MagicMock(status_code=404)


    with pytest.raises(Exception, match="511 API request failed"):
        service.get_live_bus_positions("22", "SFMTA")

# Internal method test - useful for complex logic
def test_calculate_distance(bus_service_instance):
    """Test the Haversine distance calculation."""
    service = bus_service_instance
    # Example: SF City Hall to Moscone Center (approx 0.9 miles)
    lat1, lon1 = 37.7793, -122.4193 # City Hall approx
    lat2, lon2 = 37.7839, -122.4013 # Moscone approx
    distance = service._calculate_distance(lat1, lon1, lat2, lon2)
    assert math.isclose(distance, 0.9, abs_tol=0.1) # Check within 0.1 miles

@pytest.mark.asyncio
async def test_load_stops(bus_service_instance):
    """Test loading stops from mocked file."""
    service = bus_service_instance
    service.stops_cache = None # Ensure cache is clear
    stops = await service._load_stops()
    assert isinstance(stops, list)
    assert len(stops) == 4 # Based on sample stops_csv_content
    assert stops[0]['stop_id'] == '123'
    assert stops[0]['stop_name'] == 'Stop A'
    assert service.stops_cache is not None # Cache should be populated


@pytest.mark.asyncio
async def test_find_nearby_stops(bus_service_instance):
    """Test finding nearby stops based on mocked GTFS data."""
    service = bus_service_instance
    lat, lon = 37.7752, -122.4192 # Close to A, B, D
    radius = 0.1
    limit = 2

    nearby = await service.find_nearby_stops(lat, lon, radius_miles=radius, limit=limit)

    assert isinstance(nearby, list)
    assert len(nearby) == limit # Should be limited to 2
    assert nearby[0]['stop_id'] == '123' # Stop A should be closest
    assert nearby[1]['stop_id'] == '999' # Stop D next closest
    assert 'distance_miles' in nearby[0]
    assert 'routes' in nearby[0]
    assert isinstance(nearby[0]['routes'], list)
    # Check if route info derived correctly from sample GTFS
    routes_for_stop_a = {r['route_number'] for r in nearby[0]['routes']}
    assert '1' in routes_for_stop_a
    assert '22' in routes_for_stop_a


@pytest.mark.asyncio
async def test_fetch_stop_data_real_time_success(bus_service_instance, mock_dependencies):
    """Test fetching stop data when real-time API succeeds."""
    service = bus_service_instance
    mock_get = mock_dependencies['mock_get']
    mock_response_stop = mock_dependencies['mock_response_stop']
    stop_id_to_test = "123"

    # Ensure requests.get returns the successful stop monitoring JSON
    mock_get.side_effect = lambda url, **kwargs: mock_response_stop if 'StopMonitoring' in url else MagicMock(status_code=404)


    data = await service.fetch_stop_data(stop_id_to_test)

    assert data is not None
    assert 'inbound' in data
    assert 'outbound' in data
    assert len(data['inbound']) == 1 # Based on sample JSON (within 2 hours)
    assert len(data['outbound']) == 1 # Based on sample JSON (within 2 hours)
    assert data['inbound'][0]['route_number'] == '1'
    assert data['inbound'][0]['status'] == "Delayed (1 min)" # Calculated delay
    assert data['outbound'][0]['route_number'] == '1'
    assert data['outbound'][0]['status'] == "Early (2 min)" # Calculated delay

    mock_get.assert_called_once()
    call_args, call_kwargs = mock_get.call_args
    assert f"{service.base_url}/StopMonitoring" in call_args[0]
    assert call_kwargs['params']['stopId'] == stop_id_to_test


@pytest.mark.asyncio
async def test_fetch_stop_data_real_time_fail_fallback_static(bus_service_instance, mock_dependencies):
    """Test fetch_stop_data falling back to static GTFS when real-time fails."""
    service = bus_service_instance
    mock_get = mock_dependencies['mock_get']
    stop_id_to_test = "123"

    # Configure requests.get to fail for StopMonitoring
    mock_response_fail = MagicMock()
    mock_response_fail.status_code = 500
    mock_get.side_effect = lambda url, **kwargs: mock_response_fail if 'StopMonitoring' in url else MagicMock(status_code=404)


    data = await service.fetch_stop_data(stop_id_to_test)

    # Should return static data based on sample GTFS and current time
    assert data is not None
    assert 'inbound' in data
    assert 'outbound' in data
    # Assert based on the expected static schedule filtering (IN_1_HOUR times)
    assert len(data['inbound']) > 0 # T1_In and T22_In should be inbound based on headsign
    assert len(data['outbound']) > 0 # T1_Out should be outbound
    # Check status is 'Scheduled'
    assert all(item['status'] == 'Scheduled' for item in data['inbound'])
    assert all(item['status'] == 'Scheduled' for item in data['outbound'])

@pytest.mark.asyncio
async def test_get_stop_schedule_uses_real_time_first(bus_service_instance, mocker):
    """Verify get_stop_schedule calls fetch_stop_data."""
    service = bus_service_instance
    stop_id = "123"
    mock_real_time_data = {'inbound': [{'route_number': 'RT1'}], 'outbound': []}

    # Mock fetch_stop_data directly for this test
    mock_fetch = mocker.patch.object(service, 'fetch_stop_data', return_value=mock_real_time_data)
    # Mock static schedule as well to ensure it's NOT called if real-time succeeds
    mock_static = mocker.patch.object(service, '_get_static_schedule', return_value={'inbound': [], 'outbound': []})


    schedule = await service.get_stop_schedule(stop_id)

    mock_fetch.assert_called_once_with(stop_id)
    mock_static.assert_not_called() # Should not call static if real-time has data
    assert schedule == mock_real_time_data


@pytest.mark.asyncio
async def test_get_stop_schedule_fallback(bus_service_instance, mocker):
    """Verify get_stop_schedule falls back to static if real-time returns empty."""
    service = bus_service_instance
    stop_id = "456"
    mock_empty_real_time = {'inbound': [], 'outbound': []}
    mock_static_data = {'inbound': [{'route_number': 'ST22'}], 'outbound': []} # Static data for stop 456

    mock_fetch = mocker.patch.object(service, 'fetch_stop_data', return_value=mock_empty_real_time)
    mock_static = mocker.patch.object(service, '_get_static_schedule', return_value=mock_static_data)

    schedule = await service.get_stop_schedule(stop_id)

    mock_fetch.assert_called_once_with(stop_id)
    mock_static.assert_called_once_with(stop_id) # Should call static this time
    assert schedule == mock_static_data

@pytest.mark.asyncio
async def test_get_next_buses(bus_service_instance, mocker):
    """Test get_next_buses filtering by direction."""
    service = bus_service_instance
    stop_id = "123"
    mock_data = {
        'inbound': [{'route_number': '1', 'arrival_time': '10:00 AM'}, {'route_number': '22', 'arrival_time': '10:10 AM'}],
        'outbound': [{'route_number': '1', 'arrival_time': '10:05 AM'}]
    }
    mocker.patch.object(service, 'fetch_stop_data', return_value=mock_data)

    # Test 'both'
    result_both = await service.get_next_buses(stop_id, direction="both", limit=1)
    assert 'inbound' in result_both
    assert 'outbound' in result_both
    assert len(result_both['inbound']) == 1
    assert len(result_both['outbound']) == 1

    # Test 'inbound'
    result_inbound = await service.get_next_buses(stop_id, direction="inbound", limit=2)
    assert 'inbound' in result_inbound
    assert 'outbound' not in result_inbound
    assert len(result_inbound['inbound']) == 2

    # Test 'outbound'
    result_outbound = await service.get_next_buses(stop_id, direction="outbound", limit=5)
    assert 'inbound' not in result_outbound
    assert 'outbound' in result_outbound
    assert len(result_outbound['outbound']) == 1

@pytest.mark.asyncio
async def test_get_nearby_buses_integration(bus_service_instance, mocker):
    """Test get_nearby_buses integrates find_nearby_stops and get_stop_schedule."""
    service = bus_service_instance
    lat, lon = 37.7752, -122.4192
    stop_id_a = '123'
    stop_id_d = '999'
    mock_nearby_stops = [
        {'stop_id': stop_id_a, 'stop_name': 'Stop A', 'distance_miles': 0.05, 'routes': []},
        {'stop_id': stop_id_d, 'stop_name': 'Stop D', 'distance_miles': 0.08, 'routes': []}
    ]
    mock_schedule_a = {'inbound': [{'route_number': '1A'}], 'outbound': []}
    mock_schedule_d = {'inbound': [], 'outbound': [{'route_number': '1D'}]}

    # Mock the methods called by get_nearby_buses
    mocker.patch.object(service, 'find_nearby_stops', return_value=mock_nearby_stops)
    # Mock get_stop_schedule to return different schedules based on stop_id
    async def mock_get_schedule(s_id):
        if s_id == stop_id_a: return mock_schedule_a
        if s_id == stop_id_d: return mock_schedule_d
        return None
    mocker.patch.object(service, 'get_stop_schedule', side_effect=mock_get_schedule)

    result = await service.get_nearby_buses(lat, lon, radius_miles=0.1)

    assert isinstance(result, dict)
    assert stop_id_a in result
    assert stop_id_d in result
    assert result[stop_id_a]['stop_name'] == 'Stop A'
    assert result[stop_id_a]['schedule'] == mock_schedule_a
    assert result[stop_id_d]['stop_name'] == 'Stop D'
    assert result[stop_id_d]['schedule'] == mock_schedule_d