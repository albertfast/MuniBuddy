import React, { useState, useCallback, useMemo } from 'react';
import {
  Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
  Divider, Box, Collapse, CircularProgress, Stack, Chip, IconButton,
  Button, Alert
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';

// --- Constants ---
const SCHEDULE_CACHE = {}; // Simple in-memory cache for stop schedules
const CACHE_TTL = 5 * 60 * 1000; // Cache Time-To-Live: 2 minutes in milliseconds
const API_TIMEOUT = 50000; // 50 seconds for API requests

// Retrieve API base URL from environment variables, with a fallback
const API_BASE_URL = import.meta.env.VITE_API_BASE ?? 'https://munibuddy.live/api/v1';

// --- Helper Functions ---

/**
 * Gets a consistent ID from a stop object, preferring 'stop_id'.
 * @param {object|null} stop The stop object.
 * @returns {string|number|undefined} The normalized ID or undefined.
 */
const normalizeId = (stop) => stop?.stop_id || stop?.id;

/**
 * Formats an ISO date string or potentially pre-formatted time string
 * into a locale-specific time string (e.g., "03:45 PM").
 * Handles "Unknown" and invalid date inputs gracefully.
 * @param {string} isoTime The time string to format.
 * @returns {string} The formatted time string or the original/default string.
 */
const formatTime = (isoTime) => {
  if (!isoTime || isoTime === "Unknown") return "Unknown";
  // If already formatted (e.g., "hh:mm AM/PM"), return directly
  if (/\d{1,2}:\d{2}\s[AP]M/i.test(isoTime)) return isoTime;

  try {
    const date = new Date(isoTime);
    // Check if the date object is valid
    return isNaN(date.getTime())
      ? isoTime // Return original if invalid
      : date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  } catch {
    return isoTime; // Return original on any unexpected error
  }
};

/**
 * Determines the MUI Chip color based on the route status string.
 * @param {string} status The status string (e.g., "On Time", "Late", "Early").
 * @returns {'success'|'error'|'warning'} The corresponding MUI color prop value.
 */
const getStatusColor = (status = '') => {
  const lowerStatus = status.toLowerCase();
  if (lowerStatus.includes('late')) return 'error';
  if (lowerStatus.includes('early')) return 'warning';
  return 'success'; // Default to success (includes "On Time")
};

// --- Component ---

/**
 * Displays a list of nearby transit stops and allows viewing schedules
 * for a selected stop.
 * @param {object} props - Component props.
 * @param {Array<object>|object} props.stops - An array or object containing stop data.
 */
const TransitInfo = ({ stops }) => {
  // --- State ---
  const [selectedStopId, setSelectedStopId] = useState(null); // Store only the ID
  const [stopSchedule, setStopSchedule] = useState(null); // Schedule for the selected stop
  const [loading, setLoading] = useState(false); // Loading state for API calls
  const [error, setError] = useState(null); // Error message state

  // --- Memoization ---
  // Ensure stopsArray is always an array, memoized for performance
  const stopsArray = useMemo(() => Array.isArray(stops) ? stops : Object.values(stops), [stops]);
  // Find the full selected stop object based on the ID, memoized
  // Removed unused variable 'selectedStop' to fix the compile error

  // --- Cache Management ---
  const getCachedSchedule = useCallback((stopId) => {
    const cacheItem = SCHEDULE_CACHE[stopId];
    const isCacheValid = cacheItem && (Date.now() - cacheItem.timestamp < CACHE_TTL);
    if (isCacheValid) {
      console.log(`[CACHE HIT] Stop ID: ${stopId}`);
      return cacheItem.data;
    }
    console.log(`[CACHE MISS] Stop ID: ${stopId}`);
    return null;
  }, []);

  const setCachedSchedule = useCallback((stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
    console.log(`[CACHE SET] Stop ID: ${stopId}`);
  }, []);

  // --- Event Handlers ---
  const handleStopClick = useCallback(async (stopToSelect) => {
    const stopIdToSelect = normalizeId(stopToSelect);
    console.log(`[CLICK] Stop clicked: ID ${stopIdToSelect}`);

    // If the clicked stop is already selected, deselect it
    if (selectedStopId === stopIdToSelect) {
      console.log(`[CLOSE] Deselecting stop: ${stopIdToSelect}`);
      setSelectedStopId(null);
      setStopSchedule(null); // Clear schedule
      setError(null); // Clear errors
      return;
    }

    // Select the new stop
    setSelectedStopId(stopIdToSelect);
    setLoading(true);
    setError(null);
    setStopSchedule(null); // Clear previous schedule immediately

    // Try loading from cache first
    const cachedData = getCachedSchedule(stopIdToSelect);
    if (cachedData) {
      console.log(`[LOAD] Using cached data for stop ${stopIdToSelect}`);
      setStopSchedule(cachedData);
      setLoading(false);
      return;
    }

    // Fetch from API if not in cache
    try {
      console.log(`[API] Fetching schedule from: ${API_BASE_URL}/stop-schedule/${stopIdToSelect}`);
      const response = await axios.get(`${API_BASE_URL}/stop-schedule/${stopIdToSelect}`, {
        timeout: API_TIMEOUT
      });
      console.log(`[API] Response for stop ${stopIdToSelect}:`, response.data);

      if (response.data) {
        setCachedSchedule(stopIdToSelect, response.data);
        setStopSchedule(response.data);
      } else {
        // Handle cases where API returns success but no data (or unexpected format)
        setStopSchedule({ inbound: [], outbound: [] }); // Set empty schedule
      }
    } catch (err) {
      console.error(`[ERROR] Failed to load schedule for stop ${stopIdToSelect}:`, err);
      setError('Failed to load stop schedule. Please check network or try again.');
      setStopSchedule({ inbound: [], outbound: [] }); // Ensure schedule is empty on error
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, getCachedSchedule, setCachedSchedule]); // Dependencies for useCallback

  const handleRefreshSchedule = useCallback(async () => {
    if (!selectedStopId) return; // Need a selected stop to refresh

    console.log(`[REFRESH] Manually refreshing stop ${selectedStopId}`);
    setLoading(true);
    setError(null);

    try {
      // Add cache-busting param (_t)
      const response = await axios.get(`${API_BASE_URL}/stop-schedule/${selectedStopId}`, {
        timeout: API_TIMEOUT,
        params: { _t: Date.now() } // Cache buster
      });

      console.log(`[REFRESH] New response for ${selectedStopId}:`, response.data);
      setCachedSchedule(selectedStopId, response.data);
      setStopSchedule(response.data);
    } catch (err) {
      console.error(`[ERROR] Refresh failed for stop ${selectedStopId}:`, err);
      setError('Failed to refresh schedule. Please check connection.');
      // Optionally keep the old schedule data or clear it:
      // setStopSchedule(null);
    } finally {
      setLoading(false);
    }
  }, [selectedStopId, setCachedSchedule]); // Dependencies for useCallback

  // --- Rendering Sub-Components ---

  /** Renders the primary information for a single stop in the list */
  const renderStopInfo = useCallback((stop) => (
    <>
      <Stack direction="row" alignItems="center" spacing={1} mb={0.5}>
        <LocationOnIcon color="primary" fontSize="small" />
        <Typography variant="body1" fontWeight={500} noWrap> {/* Added noWrap */}
          {stop.stop_name || 'Unknown Stop Name'}
        </Typography>
      </Stack>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box display="flex" alignItems="center">
          <DirectionsBusIcon fontSize="small" sx={{ mr: 0.5, color: 'text.secondary' }} />
          <Typography variant="caption" color="text.secondary"> {/* Changed to caption */}
            ID: {normalizeId(stop)}
          </Typography>
        </Box>
        {stop.distance_miles !== undefined && (
            <Chip
                size="small"
                label={`${stop.distance_miles} miles`}
                sx={{ height: 'auto', py: '2px', fontSize: '0.7rem', bgcolor: 'action.hover' }} // Adjusted styling
            />
        )}
      </Stack>
      {stop.routes?.length > 0 && (
        <Typography variant="caption" color="text.secondary" display="block" mt={0.5}> {/* Changed to caption */}
          Routes: {stop.routes.map(r => r.route_number || '?').join(', ')}
        </Typography>
      )}
    </>
  ), []); // Empty dependency array as it uses only the 'stop' argument

  /** Renders the details for a single scheduled route (inbound/outbound) */
  const renderRouteInfo = useCallback((route) => (
    <Box sx={{ borderLeft: '3px solid', borderColor: 'primary.light', pl: 1.5, py: 0.5, mb: 1 }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1}>
        <Typography variant="body2" fontWeight="medium" color="primary.main">
          {route.route_number || 'Route ?'} →{' '}
          <Box component="span" sx={{ color: 'text.primary', fontWeight: 'normal' }}>
            {route.destination || 'Unknown Destination'}
          </Box>
        </Typography>
        {route.status && (
            <Chip size="small" label={route.status} color={getStatusColor(route.status)} sx={{ height: 'auto', py: '2px' }} />
        )}
      </Stack>
      <Typography variant="body2" color="text.secondary" mt={0.5}>
        Arrival: <b>{formatTime(route.arrival_time)}</b>
        {route.stops_away && ` • ${route.stops_away} stops away`}
      </Typography>
    </Box>
  ), []); // Empty dependency array

  // --- Main Render ---
  return (
    <Card elevation={2} sx={{ borderRadius: 2, overflow: 'hidden' }}> {/* Added overflow */}
      <CardContent sx={{ pt: 2, pb: 1 }}> {/* Adjusted padding */}
        <Typography variant="h6" component="h2" fontWeight="bold" color="primary.main" gutterBottom>
          Nearby Stops ({stopsArray.length})
        </Typography>
        <List disablePadding> {/* Added disablePadding */}
          {stopsArray.length === 0 && (
             <ListItem>
                <ListItemText primary="No stops found in the selected area." sx={{textAlign: 'center', color: 'text.secondary'}} />
             </ListItem>
          )}
          {stopsArray.map((stop, index) => {
            const currentStopId = normalizeId(stop);
            const isSelected = selectedStopId === currentStopId;

            return (
              <React.Fragment key={currentStopId || index}> {/* Use index as fallback key */}
                <ListItemButton
                  onClick={() => handleStopClick(stop)}
                  selected={isSelected}
                  sx={{
                    borderRadius: 1,
                    mb: 0.5, // Margin between items
                    '&.Mui-selected': {
                      bgcolor: 'action.selected', // Use theme action color
                      '&:hover': { bgcolor: 'action.selected' } // Keep color on hover when selected
                    },
                    '&:hover': { // Subtle hover for non-selected items
                      bgcolor: 'action.hover'
                    },
                    py: 1.5 // Adjust vertical padding
                  }}
                  aria-expanded={isSelected} // Accessibility
                  aria-controls={`stop-details-${currentStopId}`}
                >
                  <ListItemText primary={renderStopInfo(stop)} />
                  {/* Separate button for expand/collapse icon */}
                  <IconButton
                    onClick={(e) => { e.stopPropagation(); handleStopClick(stop); }}
                    size="small"
                    aria-label={isSelected ? 'Collapse schedule' : 'Expand schedule'}
                  >
                    {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                  </IconButton>
                </ListItemButton>

                {/* Collapsible section for schedule */}
                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                  <Box
                    id={`stop-details-${currentStopId}`} // Match aria-controls
                    px={2} // Horizontal padding for content
                    pb={2} // Bottom padding for content
                    pt={1} // Top padding for content
                    sx={{ borderTop: '1px dashed', borderColor: 'divider', mx: 1, mb: 1 }} // Separator line
                  >
                    {/* Show loading spinner ONLY for the selected item */}
                    {loading && isSelected ? (
                      <Box display="flex" justifyContent="center" py={3}>
                        <CircularProgress size={32} />
                      </Box>
                    ) : /* Show schedule if loaded AND selected */
                      stopSchedule && isSelected ? (
                      <>
                        {/* Show error specific to this stop */}
                        {error && <Alert severity="warning" sx={{ mb: 2 }}>{error}</Alert>} {/* Changed severity */}

                        {/* Inbound Routes */}
                        {stopSchedule.inbound?.length > 0 && (
                          <Box mb={2}>
                            <Stack direction="row" spacing={1} mb={1} alignItems="center">
                              <ArrowDownwardIcon color="primary" />
                              <Typography variant="subtitle1" color="primary.main" fontWeight="medium">
                                Inbound
                              </Typography>
                            </Stack>
                            <List dense disablePadding>
                              {stopSchedule.inbound.map((route, i) => (
                                <ListItem key={`in-${i}`} disablePadding>
                                  <ListItemText primary={renderRouteInfo(route)} disableTypography />
                                </ListItem>
                              ))}
                            </List>
                          </Box>
                        )}

                        {/* Outbound Routes */}
                        {stopSchedule.outbound?.length > 0 && (
                          <Box>
                            <Stack direction="row" spacing={1} mb={1} alignItems="center">
                              <ArrowUpwardIcon color="primary" />
                              <Typography variant="subtitle1" color="primary.main" fontWeight="medium">
                                Outbound
                              </Typography>
                            </Stack>
                            <List dense disablePadding>
                              {stopSchedule.outbound.map((route, i) => (
                                <ListItem key={`out-${i}`} disablePadding>
                                  <ListItemText primary={renderRouteInfo(route)} disableTypography />
                                </ListItem>
                              ))}
                            </List>
                          </Box>
                        )}

                        {/* Message if no routes */}
                        {!stopSchedule.inbound?.length && !stopSchedule.outbound?.length && !error && (
                          <Typography textAlign="center" color="text.secondary" py={2}>
                            No scheduled routes found at this time.
                          </Typography>
                        )}

                        {/* Refresh Button */}
                        <Box display="flex" justifyContent="center" mt={3}>
                          <Button
                            startIcon={<RefreshIcon />}
                            onClick={handleRefreshSchedule}
                            disabled={loading} // Disable while any loading is happening
                            variant="outlined"
                            size="small"
                            sx={{ borderRadius: '20px', textTransform: 'none', px: 2 }}
                          >
                            {loading ? 'Refreshing...' : 'Refresh'}
                          </Button>
                        </Box>
                      </>
                    ) : null /* End of schedule display condition */}
                  </Box>
                </Collapse>

                {/* Divider between list items (optional aesthetic) */}
                {index < stopsArray.length - 1 && <Divider component="li" sx={{ mx: 1 }} />} {/* Indented divider */}
              </React.Fragment>
            );
          })}
        </List>
      </CardContent>
    </Card>
  );
};

export default TransitInfo;
