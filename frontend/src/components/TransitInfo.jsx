// frontend/src/components/TransitInfo.jsx
import React, { useState, useCallback, useMemo } from 'react';
import {
    Card, CardContent, Typography, List, ListItem, ListItemText, ListItemButton,
    Box, Collapse, CircularProgress, Stack, Chip, Button, Alert
} from '@mui/material';
import DirectionsBusIcon from '@mui/icons-material/DirectionsBus';
import TrainIcon from '@mui/icons-material/Train';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import RefreshIcon from '@mui/icons-material/Refresh';
import axios from 'axios';

// --- Constants and Utility Functions ---
const SCHEDULE_CACHE = {}; // Simple in-memory cache for schedules
const CACHE_TTL = 2 * 60 * 1000; // Cache time-to-live (2 minutes)
const API_TIMEOUT = 20000; // API request timeout (20 seconds)

// Get the display/cache key for a stop (uses ID prepared by App.jsx)
const normalizeIdForDisplayAndCache = (stop) => {
    return stop?.display_id_for_transit_info || stop?.stop_id || stop?.stop_code || Math.random().toString(); // Fallback to random
};

// Format ISO date string to locale time (e.g., "9:05 PM")
const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "N/A";
    try {
        const date = new Date(isoTime);
        return isNaN(date.getTime())
        ? isoTime // Return original if invalid
        : date.toLocaleTimeString('en-US', {
            hour: 'numeric', minute: '2-digit', hour12: true,
            timeZone: 'America/Los_Angeles' // Target timezone
        });
    } catch { return isoTime; }
};

// Determine Chip label and color based on minutes until arrival
const getStatusChipInfo = (minutes) => {
    if (typeof minutes !== 'number' || isNaN(minutes)) return { label: "N/A", color: "default" };
    if (minutes <= 0) return { label: "Due", color: "error" };
    if (minutes <= 5) return { label: `${minutes} min`, color: "success" };
    if (minutes <= 15) return { label: `${minutes} min`, color: "warning" };
    return { label: `${minutes} min`, color: "default" };
};

// Select Train or Bus icon based on agency or route number pattern
const renderRouteTypeIcon = (routeNumber, agency) => {
    const isBart = agency?.toLowerCase() === 'bart' || agency?.toLowerCase() === 'ba';
    const isLikelyTrain = isBart || routeNumber?.match(/^[A-Z]{2,4}(-[NSWE])?$/); // Basic BART line code check
    const IconComponent = isLikelyTrain ? TrainIcon : DirectionsBusIcon;
    return <IconComponent color="inherit" fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />;
};

// Process SIRI data: groups visits by route/destination/direction and extracts predictions
const groupAndFormatSiriPredictions = async (visits = [], agency, baseApiUrl) => {
    const routeGroups = {}; // Structure to hold grouped data

    // Helper to get nearest stop for vehicle location (optional, can be slow)
    const getVehicleNearestStop = async (lat, lon) => {
        if (!lat || !lon || !baseApiUrl) return "";
        try {
            const res = await axios.get(`${baseApiUrl}/nearby-stops`, {
                params: { lat, lon, radius: 0.1, agency: 'muni' }, timeout: 3000
            });
            return res.data?.[0]?.stop_name?.trim() || "";
        } catch (err) { return ""; }
    };

    for (const visit of visits) { // Iterate through SIRI visits
        const journey = visit?.MonitoredVehicleJourney;
        if (!journey) continue;

        // Extract relevant data from the SIRI structure
        const call = journey?.MonitoredCall || {};
        const directionRef = (journey?.DirectionRef || "0").toLowerCase();
        const directionDisplay = journey?.DirectionName || (directionRef === "0" ? "Inbound" : "Outbound");
        const lineRef = journey?.LineRef || "Unknown";
        const publishedLineName = journey?.PublishedLineName || "";
        const routeNumberDisplay = `${lineRef}${publishedLineName ? ` ${publishedLineName}` : ''}`.trim();
        const destinationDisplay = call?.DestinationDisplay || journey?.DestinationName || "Unknown Destination";
        const routeKey = `${routeNumberDisplay}_${destinationDisplay}_${directionRef}`; // Unique key for grouping

        // Initialize group if it doesn't exist
        if (!routeGroups[routeKey]) {
            const vehicleLat = journey?.VehicleLocation?.Latitude || "";
            const vehicleLon = journey?.VehicleLocation?.Longitude || "";
            const nearestStopForVehicle = ""; // await getVehicleNearestStop(vehicleLat, vehicleLon); // Fetch only if needed

            routeGroups[routeKey] = {
                route_number_display: routeNumberDisplay,
                destination: destinationDisplay,
                direction_display: directionDisplay,
                agency: agency,
                predictions: [], // Holds { arrival_time_iso, minutes_until }
                vehicle_info: { lat: vehicleLat, lon: vehicleLon, nearest_stop: nearestStopForVehicle }
            };
        }

        // Calculate minutes until arrival
        const arrivalTime = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
        const arrivalDate = arrivalTime ? new Date(arrivalTime) : null;
        const now = new Date();
        const minutesUntil = arrivalDate ? Math.max(0, Math.round((arrivalDate - now) / 60000)) : null;

        // Add prediction to the group
        if (minutesUntil !== null) {
            routeGroups[routeKey].predictions.push({
                arrival_time_iso: arrivalTime,
                minutes_until: minutesUntil,
            });
        }
    }

    // Convert grouped object back to arrays and sort
    const result = { inbound: [], outbound: [] };
    Object.values(routeGroups).forEach(group => {
        group.predictions.sort((a, b) => a.minutes_until - b.minutes_until); // Sort predictions by time
        const directionKey = (group.direction_display.toLowerCase().includes("inbound") || group.direction_display.toLowerCase() === "0")
                           ? 'inbound' : 'outbound';
        result[directionKey].push(group);
    });
    // Sort routes within each direction by the first prediction time
    result.inbound.sort((a,b) => (a.predictions[0]?.minutes_until ?? Infinity) - (b.predictions[0]?.minutes_until ?? Infinity));
    result.outbound.sort((a,b) => (a.predictions[0]?.minutes_until ?? Infinity) - (b.predictions[0]?.minutes_until ?? Infinity));
    return result;
};


// --- TransitInfo Component ---
const TransitInfo = ({ stops, setLiveVehicleMarkers, baseApiUrl }) => {
  // --- State ---
  const [selectedStopData, setSelectedStopData] = useState(null); // Holds the full data of the selected stop
  const [stopSchedule, setStopSchedule] = useState(null); // Holds the fetched schedule {inbound: [], outbound: []}
  const [loadingSchedule, setLoadingSchedule] = useState(false); // Loading state for schedule fetching
  const [scheduleError, setScheduleError] = useState(null); // Error state for schedule fetching

  // Memoize the stops array to prevent unnecessary re-renders
  const stopsArray = useMemo(() => Object.values(stops || {}), [stops]); // Ensure stops is treated as an object

  // --- Caching ---
  const getCachedSchedule = useCallback((stopId) => {
    const item = SCHEDULE_CACHE[stopId];
    return item && Date.now() - item.timestamp < CACHE_TTL ? item.data : null;
  }, []);
  const setCachedSchedule = useCallback((stopId, data) => {
    SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
  }, []);

  // --- Event Handlers ---
  // Handle clicking on a stop in the list
  const handleStopClick = useCallback(async (stopObject) => {
    const displayId = normalizeIdForDisplayAndCache(stopObject); // ID for UI state & cache
    const apiStopCode = stopObject.stop_code || displayId; // ID for API call (prefer stop_code if available)
    const agency = stopObject.agency?.toLowerCase();

    // Toggle off if the same stop is clicked again
    if (selectedStopData && normalizeIdForDisplayAndCache(selectedStopData) === displayId) {
      setSelectedStopData(null); setStopSchedule(null); setScheduleError(null);
      return;
    }

    // Set state for the newly selected stop
    setSelectedStopData(stopObject);
    setStopSchedule(null); setScheduleError(null); setLoadingSchedule(true);

    // Check cache first
    const cached = getCachedSchedule(displayId);
    if (cached) {
      setStopSchedule(cached); setLoadingSchedule(false);
      return;
    }

    // Fetch schedule from API if not cached
    try {
      const predictionURL = (agency === "bart" || agency === "ba")
          ? `${baseApiUrl}/bart-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}`
          : `${baseApiUrl}/bus-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}`;

      console.log(`[TransitInfo] Fetching schedule for ${displayId} (API code: ${apiStopCode}, Agency: ${agency})`);
      const res = await axios.get(predictionURL, { timeout: API_TIMEOUT });
      const responseData = res.data?.realtime || res.data; // Adjust based on API response wrapper
      const siriVisits = responseData?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;

      let schedule; // Variable to hold the final {inbound, outbound} schedule

      // Process based on data format
      if (Array.isArray(siriVisits)) { // SIRI Format (e.g., Muni)
        console.log(`[TransitInfo] Received SIRI format for ${displayId}. Parsing...`);
        schedule = await groupAndFormatSiriPredictions(siriVisits, agency, baseApiUrl);
      }
      else if ((agency === "bart" || agency === "ba") && responseData && responseData.inbound && responseData.outbound) {
        // Pre-grouped BART Format (as seen in console log)
        console.log(`[TransitInfo] Received pre-grouped BART format for ${displayId}. Adapting...`);
        schedule = { inbound: [], outbound: [] };

        // Adapt the structure to match the one expected by renderGroupedRouteInfo
        for (const dir of ['inbound', 'outbound']) {
          if (Array.isArray(responseData[dir])) {
            schedule[dir] = responseData[dir]
              // Map each BART route object from the API
              .map(bartRoute => ({
                route_number_display: bartRoute.route_number || "Unknown",
                destination: bartRoute.destination || "Unknown",
                direction_display: bartRoute.direction || dir, // Use provided direction or fallback
                agency: 'bart',
                // Create a 'predictions' array containing the single prediction info
                predictions: [{
                  arrival_time_iso: null, // ISO time not available in this format
                  minutes_until: typeof bartRoute.minutes_until === 'number' ? bartRoute.minutes_until : parseInt(bartRoute.arrival_time, 10) // Use number or parse string
                }].filter(p => typeof p.minutes_until === 'number' && !isNaN(p.minutes_until)), // Ensure valid minutes
                // Create a dummy vehicle_info as it's not present in this format
                vehicle_info: { lat: "", lon: "", nearest_stop: "" }
              }))
              // Filter out routes that didn't yield a valid prediction after parsing
              .filter(group => group.predictions.length > 0);

            // Sort the adapted routes by minutes_until within the direction
            schedule[dir].sort((a, b) => (a.predictions[0]?.minutes_until ?? Infinity) - (b.predictions[0]?.minutes_until ?? Infinity));
          }
        }
         console.log("[TransitInfo] Adapted BART schedule:", schedule);
      }
      else { // Unexpected format
        console.error(`[TransitInfo] Unexpected data format for ${displayId}. Response:`, responseData);
        throw new Error("Received unexpected data format from API.");
      }

      // Final check to ensure schedule has the correct structure
      if (!schedule || !schedule.inbound || !schedule.outbound || !Array.isArray(schedule.inbound) || !Array.isArray(schedule.outbound)) {
        console.warn("[TransitInfo] Parsing resulted in invalid schedule structure. Defaulting to empty.", schedule);
        schedule = { inbound: [], outbound: [] };
      }

      setCachedSchedule(displayId, schedule); // Cache the result
      setStopSchedule(schedule); // Update state

    } catch (err) { // Handle fetch/processing errors
      console.error(`[TransitInfo] Failed fetch/process for ${displayId}:`, err);
      setScheduleError(`Failed to load schedule. ${err.message}`);
      setStopSchedule({ inbound: [], outbound: [] }); // Set empty schedule on error
    } finally {
      setLoadingSchedule(false); // Always finish loading
    }
  }, [selectedStopData, getCachedSchedule, setCachedSchedule, baseApiUrl]); // Dependencies

  // Refresh schedule handler
  const handleRefreshSchedule = useCallback(async () => {
    if (!selectedStopData) return;
    const displayId = normalizeIdForDisplayAndCache(selectedStopData);
    console.log(`[TransitInfo] Refresh triggered for ${displayId}`);
    delete SCHEDULE_CACHE[displayId]; // Invalidate cache
    await handleStopClick(selectedStopData); // Trigger fetch again
  }, [selectedStopData, handleStopClick]);

  // Render function for a single route group (handles multiple predictions)
  const renderGroupedRouteInfo = (routeGroup) => {
    // Extract valid prediction minutes
    const predictionMinutes = routeGroup.predictions
      .map(p => p.minutes_until)
      .filter(mins => typeof mins === 'number' && !isNaN(mins));

    // Create labels like "Due", "5 min"
    const predictionLabels = predictionMinutes.map(mins => getStatusChipInfo(mins).label);

    // Get info for the first prediction (for chip color and main time)
    const firstPredictionMinutes = predictionMinutes[0];
    const chipInfoForFirst = getStatusChipInfo(firstPredictionMinutes);

    // Determine arrival time text to display
    const nextArrivalTimeText = routeGroup.predictions[0]?.arrival_time_iso
      ? formatTime(routeGroup.predictions[0].arrival_time_iso) // Format if ISO time exists
      : (typeof firstPredictionMinutes === 'number' ? `in ${firstPredictionMinutes} min` : 'N/A'); // Otherwise show minutes

    return (
      <Box className="route-info-box"> {/* Container for route details */}
        {/* Top Row: Icon, Route Name, Destination, Prediction Chip */}
        <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={0.5}>
          <Typography variant="h6" component="div" className="route-title" noWrap sx={{ flexGrow: 1, mr: 1 }}>
            {renderRouteTypeIcon(routeGroup.route_number_display, routeGroup.agency)}
            {routeGroup.route_number_display}
            <Typography component="span" className="route-destination">
              {' '}→ {routeGroup.destination}
            </Typography>
          </Typography>
          {/* Combined Prediction Chip (e.g., "Due / 5 min / 15 min") */}
          <Chip
            size="small"
            label={predictionLabels.length > 0 ? predictionLabels.slice(0, 3).join(' / ') : "N/A"} // Show first 3 predictions
            color={chipInfoForFirst.color} // Color based on the *first* arrival
            sx={{ fontWeight: 'bold', fontSize: '0.75rem', flexShrink: 0 }}
          />
        </Stack>
        {/* Second Row: Formatted time of next arrival */}
        <Typography variant="body2" className="route-arrival-detail">
          Next at: {nextArrivalTimeText}
        </Typography>
        {/* Third Row: Vehicle location info (if available) */}
        {routeGroup.vehicle_info?.nearest_stop && (
          <Typography variant="caption" className="route-vehicle-location">
            Vehicle near: {routeGroup.vehicle_info.nearest_stop}
          </Typography>
        )}
        {/* Show "unavailable" only if predictions exist but vehicle info doesn't */}
        {(!routeGroup.vehicle_info?.nearest_stop && predictionMinutes.length > 0) && (
          <Typography variant="caption" className="route-vehicle-location-unavailable">
            Real-time vehicle location unavailable
          </Typography>
        )}
      </Box>
    );
  };

  // --- Main Component Render ---
  return (
    <Card elevation={0} className="transit-card-custom">
      <CardContent sx={{ p: { xs: 1, sm: 1.5 } }}> {/* Adjust padding */}
        {/* Section Header */}
        <Typography className="transit-section-header" sx={{ pl: { xs: 0, sm: 1 } }}>
          Nearby Stops ({stopsArray.length})
        </Typography>

        {/* Message if no stops */}
        {stopsArray.length === 0 && !loadingSchedule && (
          <Typography align="center" color="text.secondary" sx={{ py: 3 }}>
            No stops found nearby. Adjust search or radius.
          </Typography>
        )}

        {/* List of Stops */}
        <List disablePadding>
          {stopsArray.map((stop) => {
            const uniqueKeyAndDisplayId = normalizeIdForDisplayAndCache(stop); // Unique ID for this stop
            const isSelected = selectedStopData && (normalizeIdForDisplayAndCache(selectedStopData) === uniqueKeyAndDisplayId);

            return (
              <React.Fragment key={uniqueKeyAndDisplayId}> {/* Use the unique ID as key */}
                {/* Stop Item Button */}
                <ListItemButton
                  onClick={() => handleStopClick(stop)}
                  sx={{ pt: 1, pb: 1, borderRadius: '4px', '&:hover': { backgroundColor: 'action.hover' }, mb: 0.5 }}
                >
                  <Box flexGrow={1}>
                    {/* Stop Name & Icon */}
                    <Stack direction="row" spacing={1} alignItems="center" mb={0.25}>
                      <LocationOnIcon color="primary" fontSize="small" />
                      <Typography fontWeight={500} noWrap sx={{ fontSize: '0.95rem' }}>
                        {stop.stop_name || 'Unknown Stop'}
                      </Typography>
                    </Stack>
                    {/* Stop ID & Distance */}
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                        ID: {stop.stop_code || uniqueKeyAndDisplayId.replace(/-bart$/i, '').replace(/-muni$/i, '')}
                      </Typography>
                      {stop.distance_miles !== undefined && (
                        <Chip component="span" size="small" label={`${parseFloat(stop.distance_miles).toFixed(3)} mi`} sx={{ fontSize: '0.7rem', height: '18px', mr: 1 }} />
                      )}
                    </Stack>
                  </Box>
                  {/* Expand/Collapse Icon */}
                  {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>

                {/* Collapsible Schedule Section */}
                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                  <Box px={{ xs: 1, sm: 1.5 }} pb={1.5} pt={1} sx={{ borderLeft: '3px solid var(--purpleLight)', ml: { xs: 0.5, sm: 1 }, mr: { xs: 0.5, sm: 1 }, mb: 1 }}>
                    {/* Refresh Button */}
                    <Button
                      startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} disabled={loadingSchedule} size="small"
                      sx={{ mb: 1.5, textTransform: 'none', color: 'var(--purple)', '&:hover': { backgroundColor: 'var(--purpleLight)' } }}
                    >
                      {loadingSchedule && isSelected ? "Refreshing..." : "Refresh"}
                    </Button>

                    {/* Loading Indicator */}
                    {loadingSchedule && isSelected && ( <Box py={3} display="flex" justifyContent="center"><CircularProgress size={28} /></Box> )}
                    {/* Error Message */}
                    {scheduleError && isSelected && ( <Alert severity="error" sx={{ fontSize: '0.85rem' }}>{scheduleError}</Alert> )}

                    {/* Schedule Display (only if not loading, no error, schedule exists, and this stop is selected) */}
                    {!loadingSchedule && !scheduleError && stopSchedule && isSelected && (
                      <>
                        {/* Iterate through Inbound and Outbound */}
                        {['inbound', 'outbound'].map((dirKey) => (
                          // Ensure the direction array exists and has routes
                          stopSchedule[dirKey] && Array.isArray(stopSchedule[dirKey]) && stopSchedule[dirKey].length > 0 && (
                            <Box key={dirKey} mb={2}>
                              <Typography variant="overline" display="block" gutterBottom sx={{ color: 'var(--current-grayMid-val)', fontSize: '0.7rem', fontWeight: 'bold' }}>
                                {dirKey.toUpperCase()}
                              </Typography>
                              <List dense disablePadding>
                                {/* Map through routes in this direction */}
                                {stopSchedule[dirKey].map((routeGroup, i) => (
                                  <ListItem key={`${dirKey}-${routeGroup.route_number_display}-${routeGroup.destination}-${i}`} disablePadding className="transit-list-item-custom">
                                    <ListItemText primary={renderGroupedRouteInfo(routeGroup)} disableTypography />
                                  </ListItem>
                                ))}
                              </List>
                            </Box>
                          )
                        ))}
                        {/* Message if schedule is loaded but both directions are empty */}
                        {(stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0) && (
                          <Typography className="transit-empty" sx={{ fontSize: '0.9rem' }}>No upcoming transit found.</Typography>
                        )}
                      </>
                    )}
                     {/* Fallback message if schedule is null after loading without error */}
                    {!loadingSchedule && !scheduleError && !stopSchedule && isSelected && (
                        <Typography variant="body2" color="text.secondary">Schedule data unavailable.</Typography>
                    )}
                  </Box>
                </Collapse>
              </React.Fragment>
            );
          })}
        </List>
      </CardContent>
    </Card>
  );
};

export default TransitInfo;