# optimized_transit_router.py

import heapq
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

from geopy.distance import great_circle
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session, scoped_session
from sqlalchemy import create_engine  # Import create_engine
from sqlalchemy.orm import sessionmaker  # Import sessionmaker

# Update these imports according to your project structure
from models import UserQuery, Stop  # Assuming you have SQLAlchemy models defined
from utils import config, timer  # Assuming you have a config and timer utility

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

class TransitRouter:
    """
    Optimized Transit Router class with ALT (A* with Landmarks), PostgreSQL, Redis, and pgRouting integration.
    """
    def __init__(self, db_url: str, redis_host: str, redis_port: int, landmark_stop_ids: List[str], walk_speed: float, transfer_penalty: int):
        """
        Initializes the TransitRouter with database and Redis connections, landmark stops, and routing parameters.

        Args:
            db_url (str): PostgreSQL database connection URL.
            redis_host (str): Redis host address.
            redis_port (int): Redis port number.
            landmark_stop_ids (List[str]): List of stop IDs to use as landmarks for the ALT heuristic.
            walk_speed (float): Walking speed in meters per second.
            transfer_penalty (int): Transfer penalty in seconds.
        """

        try:
            engine = create_engine(db_url, pool_size=20, max_overflow=10)  # Initialize the engine
            self.session_factory = sessionmaker(bind=engine)
            self.Session = scoped_session(self.session_factory)  # Use scoped_session
            self.redis = Redis(host=redis_host, port=redis_port, decode_responses=True)  # Initialize Redis
        except Exception as e:
            logger.error(f"Failed to connect to database or Redis: {e}", exc_info=True)
            raise  # Re-raise the exception to prevent the application from running without connections

        self.landmarks = landmark_stop_ids
        self.walk_speed = walk_speed  # m/s
        self.transfer_penalty = transfer_penalty  # seconds
        self.landmark_distances = self._get_cached_landmarks() or self.precompute_landmarks()  # Initialize landmark distances

    def __enter__(self):
        """
        Context manager to handle database sessions.
        """
        self.session = self.Session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Closes the database session.
        """
        self.Session.remove()

    @timer
    def _get_cached_landmarks(self) -> Optional[Dict[str, Dict[str, float]]]:
        """
        Retrieves landmark distances from Redis cache.
        """
        try:
            cached = self.redis.get(config.LANDMARK_CACHE_KEY)
            if cached:
                logger.info("Loaded landmarks from cache.")
                return json.loads(cached)
            logger.info("No landmarks in cache.")
            return None
        except Exception as e:
            logger.error(f"Error getting landmarks from cache: {e}", exc_info=True)
            return None

    @timer
    def _cache_landmarks(self, landmarks: Dict[str, Dict[str, float]]) -> None:
        """
        Caches landmark distances to Redis.
        """
        try:
            self.redis.set(config.LANDMARK_CACHE_KEY, json.dumps(landmarks))
            logger.info("Cached landmark distances.")
        except Exception as e:
            logger.error(f"Error caching landmarks: {e}", exc_info=True)

    @timer
    def precompute_landmarks(self) -> Dict[str, Dict[str, float]]:
        """
        Precomputes landmark distances using Dijkstra's algorithm from database.
        """
        landmark_distances = {}
        for lm in self.landmarks:
            landmark_distances[lm] = self._db_dijkstra(lm)
        self._cache_landmarks(landmark_distances)
        return landmark_distances

    @timer
    def _db_dijkstra(self, start_node: str) -> Dict[str, float]:
        """
        Dijkstra's algorithm using direct database queries.
        """
        distances = {start_node: 0.0}
        priority_queue = [(0.0, start_node)]

        while priority_queue:
            dist, current_node = heapq.heappop(priority_queue)

            if dist > distances.get(current_node, float('inf')):
                continue

            neighbors = self._get_neighbors(current_node)
            for neighbor, edge_data in neighbors:
                new_cost = dist + self._calculate_edge_cost(edge_data)
                if new_cost < distances.get(neighbor, float('inf')):
                    distances[neighbor] = new_cost
                    heapq.heappush(priority_queue, (new_cost, neighbor))
        return distances

    @timer
    def _find_nearby_stops(self, lat: float, lon: float, radius: float) -> List[str]:
        """
        Finds nearby stops within a given radius using PostGIS.
        """
        try:
            # Using SQLAlchemy Core to execute raw SQL queries
            query = text("""
                SELECT stop_id
                FROM stops
                WHERE ST_DWithin(geog, ST_MakePoint(:lon, :lat)::geography, :radius)
            """)
            result = self.session.execute(query, {"lat": lat, "lon": lon, "radius": radius}).fetchall()
            stop_ids = [row[0] for row in result]
            logger.info(f"Found {len(stop_ids)} stops nearby.")
            return stop_ids
        except Exception as e:
            logger.error(f"Error finding nearby stops: {e}", exc_info=True)
            return []

    @timer
    def find_route(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> List[dict]:
        """
        Finds the best route between two geo-coordinates.
        """
        start_stops = self._find_nearby_stops(start_lat, start_lon, config.WALKING_RADIUS)
        end_stops = self._find_nearby_stops(end_lat, end_lon, config.WALKING_RADIUS)

        if not start_stops or not end_stops:
            logger.warning("No nearby stops found for start or end location.")
            return []

        route = self._alt_search(start_stops, end_stops)

        self._log_query(start_lat, start_lon, end_lat, end_lon, route)
        return route

    def _log_query(self, start_lat: float, start_lon: float, end_lat: float, end_lon: float, route: List[dict]) -> None:
        """
        Logs user queries into the database.
        """
        try:
            query = UserQuery(
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon,
                route=json.dumps(route)  # Store the route as JSON
            )
            self.session.add(query)
            self.session.commit()
            logger.info("User query logged.")
        except Exception as e:
            logger.error(f"Error logging user query: {e}", exc_info=True)
            self.session.rollback()  # Rollback in case of error

    @timer
    def _alt_search(self, start_stops: List[str], end_stops: List[str]) -> List[dict]:
        """
        Complete ALT Algorithm Implementation with:
        - Bidirectional search
        - Landmark-based heuristic
        - Transfer penalty handling
        - Hybrid database/memory graph traversal
        """
        # Initialize priority queues
        forward_queue = []
        backward_queue = []

        # Initialize search states
        forward_g = {stop: float('inf') for stop in self._get_all_stops()}  # Initialize with infinity
        backward_g = {stop: float('inf') for stop in self._get_all_stops()} # Initialize with infinity
        for stop in start_stops:
            forward_g[stop] = 0
        for stop in end_stops:
            backward_g[stop] = 0

        came_from_forward = {}
        came_from_backward = {}

        # Initialize with start and end nodes
        for stop in start_stops:
            heapq.heappush(forward_queue, (
                self._heuristic(stop, end_stops, forward=True),
                0,  # g-score
                stop
            ))

        for stop in end_stops:
            heapq.heappush(backward_queue, (
                self._heuristic(stop, start_stops, forward=False),
                0,  # g-score
                stop
            ))

        best_path = None
        best_cost = float('inf')

        while forward_queue and backward_queue:
            # Forward search iteration
            if forward_queue[0][0] <= backward_queue[0][0]: # Check f_score to decide direction
                _, g_forward, current = heapq.heappop(forward_queue)

                if current in backward_g and g_forward + backward_g[current] < best_cost:
                    best_cost = g_forward + backward_g[current]
                    best_path = self._merge_paths(
                        current,
                        came_from_forward,
                        came_from_backward
                    )

                # Expand forward
                for neighbor, edge_data in self._get_neighbors(current):
                    new_g = g_forward + self._calculate_edge_cost(edge_data)

                    # Apply transfer penalty if needed
                    if 'transfer' in edge_data:
                        new_g += self.transfer_penalty

                    if neighbor not in forward_g or new_g < forward_g[neighbor]:
                        forward_g[neighbor] = new_g
                        f_score = new_g + self._heuristic(neighbor, end_stops, forward=True)
                        heapq.heappush(forward_queue, (f_score, new_g, neighbor))
                        came_from_forward[neighbor] = current
            else:
                # Backward search iteration (similar logic)
                _, g_backward, current = heapq.heappop(backward_queue)

                if current in forward_g and g_backward + forward_g[current] < best_cost:
                    best_cost = g_backward + forward_g[current]
                    best_path = self._merge_paths(
                        current,
                        came_from_forward,
                        came_from_backward
                    )

                # Expand backward
                for neighbor, edge_data in self._get_neighbors(current):
                    new_g = g_backward + self._calculate_edge_cost(edge_data)

                    # Apply transfer penalty if needed
                    if 'transfer' in edge_data:
                        new_g += self.transfer_penalty

                    if neighbor not in backward_g or new_g < backward_g[neighbor]:
                        backward_g[neighbor] = new_g
                        f_score = new_g + self._heuristic(neighbor, start_stops, forward=False)
                        heapq.heappush(backward_queue, (f_score, new_g, neighbor))
                        came_from_backward[neighbor] = current

        return self._format_path(best_path) if best_path else []

    @timer
    def _heuristic(self, node: str, targets: List[str], forward: bool) -> float:
        """
        Landmark-based heuristic using triangle inequality.
        """
        if not self.landmark_distances:
            logger.warning("No landmark distances available, using zero heuristic")
            return 0

        max_h = 0
        for lm in self.landmarks:
            if lm not in self.landmark_distances:
                continue

            if node not in self.landmark_distances[lm] or targets[0] not in self.landmark_distances[lm]:
                continue  # If landmark is not reachable, move on.

            if forward:
                h = self.landmark_distances[lm][node] - self.landmark_distances[lm][targets[0]]
            else:
                h = self.landmark_distances[lm][targets[0]] - self.landmark_distances[lm][node]

            max_h = max(max_h, abs(h))

        return max_h

    @timer
    def _get_neighbors(self, stop_id: str) -> List[Tuple[str, dict]]:
        """
        Hybrid neighbor lookup:
        1. Check Redis cache for frequent connections
        2. Query PostgreSQL for other connections
        3. Generate walking edges dynamically
        """
        neighbors = []

        # Check cached connections
        cache_key = f"connections:{stop_id}"
        try:
            if cached := self.redis.get(cache_key):
                neighbors.extend(json.loads(cached))
        except Exception as e:
            logger.error(f"Error getting connections from Redis: {e}", exc_info=True)

        # Query database for scheduled transit
        try:
            query = """
                SELECT to_stop,
                       EXTRACT(EPOCH FROM (departure_time - arrival_time)) AS duration,
                       route_id,
                       trip_id
                FROM scheduled_connections
                WHERE from_stop = :stop_id
                ORDER BY departure_time
            """
            result = self.session.execute(text(query), {"stop_id": stop_id}).fetchall()
            neighbors.extend([(
                row[0],
                {"type": "transit", "duration": row[1], "route": row[2], "trip": row[3]}
            ) for row in result])
        except Exception as e:
            logger.error(f"Error querying database for scheduled transit: {e}", exc_info=True)

        # Add dynamic walking edges
        try:
            walking_neighbors = self._find_walking_neighbors(stop_id)
            neighbors.extend(walking_neighbors)
        except Exception as e:
            logger.error(f"Error finding walking neighbors: {e}", exc_info=True)

        return neighbors

    @timer
    def _find_walking_neighbors(self, stop_id: str) -> List[Tuple[str, dict]]:
        """
        Find walkable stops using PostGIS and street network analysis.
        """
        query = """
            SELECT s2.stop_id,
                   ST_Distance(s1.geog, s2.geog) / :speed AS duration
            FROM stops s1, stops s2
            WHERE s1.stop_id = :stop_id
            AND ST_DWithin(s1.geog, s2.geog, :walking_range)
            AND s1.stop_id <> s2.stop_id
        """
        params = {
            "stop_id": stop_id,
            "speed": self.walk_speed,
            "walking_range": config.MAX_WALKING_DISTANCE
        }
        try:
            result = self.session.execute(text(query), params).fetchall()
            return [
                (row[0], {"type": "walking", "duration": row[1]})
                for row in result
            ]
        except Exception as e:
            logger.error(f"Error finding walking neighbors with PostGIS: {e}", exc_info=True)
            return []

    def _calculate_edge_cost(self, edge_data: dict) -> float:
        """
        Calculate edge cost considering real-time factors.
        """
        base_cost = edge_data.get("duration", 0)

        # Add real-time delay if available
        if "trip" in edge_data:
            delay = self._get_realtime_delay(edge_data["trip"])
            base_cost += delay

        return base_cost

    def _get_realtime_delay(self, trip_id: str) -> float:
        """
        Check real-time updates from Redis.
        """
        delay_key = f"rt_delay:{trip_id}"
        try:
            delay = float(self.redis.get(delay_key) or 0)
            return delay
        except Exception as e:
            logger.error(f"Error getting real-time delay from Redis: {e}", exc_info=True)
            return 0.0

    def _merge_paths(self, meeting_point: str,
                    forward_path: Dict, backward_path: Dict) -> List[str]:
        """
        Merge bidirectional search results.
        """
        forward_segment = self._reconstruct_path(meeting_point, forward_path)
        backward_segment = self._reconstruct_path(meeting_point, backward_path)
        return forward_segment[:-1] + backward_segment[::-1]

    def _reconstruct_path(self, end_node: str, came_from: Dict) -> List[str]:
        """
        Reconstruct path from search tree.
        """
        path = []
        current = end_node
        while current in came_from:
            path.append(current)
            current = came_from[current]
        path.append(current)
        return path[::-1]

    def _format_path(self, path: List[str]) -> List[dict]:
        """
        Enrich path with stop details and instructions.
        """
        formatted = []
        try:
            for stop_id in path:
                # Using SQLAlchemy Core to execute raw SQL queries
                query = text("""
                    SELECT stop_name, stop_lat, stop_lon
                    FROM stops
                    WHERE stop_id = :stop_id
                """)
                result = self.session.execute(query, {"stop_id": stop_id}).fetchone()
                if result:
                    stop_name, stop_lat, stop_lon = result
                    formatted.append({
                        "stop_id": stop_id,
                        "name": stop_name,
                        "lat": stop_lat,
                        "lon": stop_lon,
                        "type": "transit"  # Will be updated based on edge data
                    })
        except Exception as e:
            logger.error(f"Error formatting path: {e}", exc_info=True)
        return formatted

    @timer
    def _get_all_stops(self) -> List[str]:
        """
        Retrieves all stop IDs from the database.
        """
        try:
            # Using SQLAlchemy Core to execute raw SQL queries
            query = text("SELECT stop_id FROM stops")
            result = self.session.execute(query).fetchall()
            return [row[0] for row in result]
        except Exception as e:
            logger.error(f"Error getting all stop IDs: {e}", exc_info=True)
            return []

def main():
    """
    Main function to run the transit router.
    """
    # Load configuration from utils.config
    db_url = config.DATABASE_URL
    redis_host = config.REDIS_HOST
    redis_port = config.REDIS_PORT
    landmark_stop_ids = config.LANDMARK_STOP_IDS
    walk_speed = config.WALK_SPEED
    transfer_penalty = config.TRANSFER_PENALTY

    # Example usage:
    try:
        # Use a context manager to manage the session
        with TransitRouter(db_url, redis_host, redis_port, landmark_stop_ids, walk_speed, transfer_penalty) as router:
            # Find route from start to end locations
            start_lat = 37.7749
            start_lon = -122.4194
            end_lat = 34.0522
            end_lon = -118.2437
            route = router.find_route(start_lat, start_lon, end_lat, end_lon)

            if route:
                print("Route found:")
                for stop in route:
                    print(stop)
            else:
                print("No route found.")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)

if __name__ == "__main__":
    main()