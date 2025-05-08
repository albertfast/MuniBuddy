// frontend/src/components/TransitInfo.jsx
import React, { useState, useCallback, useMemo, useRef, useEffect } from 'react';
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
const SCHEDULE_CACHE = {};
const CACHE_TTL = 2 * 60 * 1000; // 2 minute cache
const API_TIMEOUT = 20000; // API request timeout

// Get display/cache key (uses ID prepared by App.jsx)
const normalizeIdForDisplayAndCache = (stop) => {
    return stop?.display_id_for_transit_info || stop?.stop_id || stop?.stop_code || Math.random().toString();
};

// Format ISO time string
const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "N/A";
    try {
        const date = new Date(isoTime);
        return isNaN(date.getTime())
        ? isoTime
        : date.toLocaleTimeString('en-US', {
            hour: 'numeric', minute: '2-digit', hour12: true,
            timeZone: 'America/Los_Angeles'
        });
    } catch { return isoTime; }
};

// Determine chip style based on minutes
const getStatusChipInfo = (minutes) => {
    if (typeof minutes !== 'number' || isNaN(minutes)) return { label: "N/A", color: "default" };
    if (minutes <= 0) return { label: "Due", color: "error" };
    if (minutes <= 5) return { label: `${minutes} min`, color: "success" };
    if (minutes <= 15) return { label: `${minutes} min`, color: "warning" };
    return { label: `${minutes} min`, color: "default" };
};

// Render appropriate icon
const renderRouteTypeIcon = (routeNumber, agency) => {
    const isBart = agency?.toLowerCase() === 'bart' || agency?.toLowerCase() === 'ba';
    const isLikelyTrain = isBart || routeNumber?.match(/^[A-Z]{2,4}(-[NSWE])?$/);
    const IconComponent = isLikelyTrain ? TrainIcon : DirectionsBusIcon;
    return <IconComponent color="inherit" fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />;
};

// Fetches nearest stop name based on coordinates
// NOTE: Calling this frequently can impact performance and API usage.
const getNearestStopName = async (lat, lon, baseApiUrl) => {
    if (!lat || !lon || !baseApiUrl) return ""; // Guard clause
    // Simple cache for nearest stop names to reduce API calls within a short timeframe
    const cacheKey = `${lat.toFixed(4)},${lon.toFixed(4)}`;
    const nearestStopCache = window.nearestStopCache || {}; // Use a simple window cache (or a more robust solution)
    window.nearestStopCache = nearestStopCache; // Ensure it's assigned back
    const now = Date.now();
    if (nearestStopCache[cacheKey] && (now - nearestStopCache[cacheKey].timestamp < 60000)) { // 1 min cache
        // console.log("[getNearestStopName] Cache hit for:", cacheKey);
        return nearestStopCache[cacheKey].name;
    }

    try {
        // console.log("[getNearestStopName] API call for:", cacheKey);
        const res = await axios.get(`${baseApiUrl}/nearby-stops`, {
            params: { lat, lon, radius: 0.1, agency: 'muni' }, // Small radius for vehicle
            timeout: 4000 // Shorter timeout
        });
        const name = res.data?.[0]?.stop_name?.trim() || "";
        nearestStopCache[cacheKey] = { name: name, timestamp: now }; // Update cache
        return name;
    } catch (err) {
        console.warn('[getNearestStopName] Error fetching nearest stop:', err.message);
        nearestStopCache[cacheKey] = { name: "", timestamp: now }; // Cache empty result on error too
        return ""; // Return empty string on error
    }
};


// Process SIRI data (Muni) AND Adapt pre-grouped BART data
const processAndGroupScheduleData = async (responseData, agency, baseApiUrl) => {
    const routeGroups = {}; // key: "routeNum_destination_direction"
    const finalSchedule = { inbound: [], outbound: [] };
    const siriVisits = responseData?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;

    // --- Processing Logic ---
    if (Array.isArray(siriVisits)) { // Process SIRI Format (Muni, etc.)
        console.log("[processAndGroupScheduleData] Processing SIRI visits...");
        for (const visit of siriVisits) {
            const journey = visit?.MonitoredVehicleJourney;
            if (!journey) continue;
            const call = journey?.MonitoredCall || {};
            const directionRef = (journey?.DirectionRef || "0").toLowerCase();
            const directionDisplay = journey?.DirectionName || (directionRef === "0" ? "Inbound" : "Outbound");
            const lineRef = journey?.LineRef || "Unknown";
            const publishedLineName = journey?.PublishedLineName || "";
            const routeNumberDisplay = `${lineRef}${publishedLineName ? ` ${publishedLineName}` : ''}`.trim();
            const destinationDisplay = call?.DestinationDisplay || journey?.DestinationName || "Unknown";
            const routeKey = `${routeNumberDisplay}_${destinationDisplay}_${directionRef}`;

            if (!routeGroups[routeKey]) {
                const vehicleLat = journey?.VehicleLocation?.Latitude || "";
                const vehicleLon = journey?.VehicleLocation?.Longitude || "";
                // Fetch nearest stop ONCE per group, using first vehicle's location
                const nearestStopForVehicle = await getNearestStopName(vehicleLat, vehicleLon, baseApiUrl);

                routeGroups[routeKey] = {
                    route_number_display: routeNumberDisplay, destination: destinationDisplay,
                    direction_display: directionDisplay, agency: agency, predictions: [],
                    vehicle_info: { lat: vehicleLat, lon: vehicleLon, nearest_stop: nearestStopForVehicle }
                };
            }
            const arrivalTime = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
            const arrivalDate = arrivalTime ? new Date(arrivalTime) : null;
            const now = new Date();
            const minutesUntil = arrivalDate ? Math.max(0, Math.round((arrivalDate - now) / 60000)) : null;

            if (minutesUntil !== null) {
                routeGroups[routeKey].predictions.push({ arrival_time_iso: arrivalTime, minutes_until: minutesUntil });
            }
        }
    } else if ((agency === "bart" || agency === "ba") && responseData && responseData.inbound && responseData.outbound) {
        // Process Pre-Grouped BART Format
        console.log("[processAndGroupScheduleData] Processing pre-grouped BART data...");
        for (const dir of ['inbound', 'outbound']) {
            if (Array.isArray(responseData[dir])) {
                responseData[dir].forEach(bartRoute => {
                    const routeNumberDisplay = bartRoute.route_number || "Unknown";
                    const destinationDisplay = bartRoute.destination || "Unknown";
                    const directionDisplay = bartRoute.direction || dir;
                    // Assume directionRef matches dir for key uniqueness
                    const routeKey = `${routeNumberDisplay}_${destinationDisplay}_${dir}`;
                    const minutesUntil = typeof bartRoute.minutes_until === 'number' ? bartRoute.minutes_until : parseInt(bartRoute.arrival_time, 10);

                    if (!isNaN(minutesUntil)) {
                         // Initialize group if it doesn't exist (BART format doesn't provide vehicle coords)
                        if (!routeGroups[routeKey]) {
                            routeGroups[routeKey] = {
                                route_number_display: routeNumberDisplay, destination: destinationDisplay,
                                direction_display: directionDisplay, agency: 'bart', predictions: [],
                                vehicle_info: { lat: "", lon: "", nearest_stop: "" } // No vehicle info from this format
                            };
                        }
                        routeGroups[routeKey].predictions.push({
                            arrival_time_iso: null, // Not available
                            minutes_until: minutesUntil
                        });
                    }
                });
            }
        }
    } else {
        console.warn("[processAndGroupScheduleData] Unrecognized data format:", responseData);
        // Return empty schedule if format is unknown
        return { inbound: [], outbound: [] };
    }

    // --- Final Grouping, Sorting, and Formatting ---
    Object.values(routeGroups).forEach(group => {
        group.predictions.sort((a, b) => a.minutes_until - b.minutes_until); // Sort predictions
        // Determine direction key based on naming convention or reference
        const directionKey = (group.direction_display.toLowerCase().includes("inbound") || group.direction_display.toLowerCase().includes("0"))
            ? 'inbound'
            : 'outbound';
        finalSchedule[directionKey].push(group);
    });
    // Sort routes within each direction
    finalSchedule.inbound.sort((a, b) => (a.predictions[0]?.minutes_until ?? Infinity) - (b.predictions[0]?.minutes_until ?? Infinity));
    finalSchedule.outbound.sort((a, b) => (a.predictions[0]?.minutes_until ?? Infinity) - (b.predictions[0]?.minutes_until ?? Infinity));

    return finalSchedule;
};


// --- Component ---
const TransitInfo = ({ stops, setLiveVehicleMarkers, baseApiUrl }) => {
  const [selectedStopData, setSelectedStopData] = useState(null);
  const [stopSchedule, setStopSchedule] = useState(null);
  const [loadingSchedule, setLoadingSchedule] = useState(false);
  const [scheduleError, setScheduleError] = useState(null);
  const listRef = useRef(null); // Ref for the List component
  const selectedItemRef = useRef(null); // Ref for the selected ListItem

  const stopsArray = useMemo(() => Object.values(stops || {}), [stops]);

  // --- Caching Callbacks ---
  const getCachedSchedule = useCallback((stopId) => { /* ... (same as before) ... */
        const item = SCHEDULE_CACHE[stopId];
        return item && Date.now() - item.timestamp < CACHE_TTL ? item.data : null;
    }, []);
  const setCachedSchedule = useCallback((stopId, data) => { /* ... (same as before) ... */
        SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
    }, []);

  // --- Scroll to Selected Item ---
  // Use useEffect to scroll after the component re-renders with the selection
  useEffect(() => {
    if (selectedItemRef.current && listRef.current) {
      // Use timeout to ensure rendering is complete before scrolling
      const timer = setTimeout(() => {
        if (selectedItemRef.current) { // Check again inside timeout
          selectedItemRef.current.scrollIntoView({
            behavior: 'smooth',
            block: 'nearest', // Scrolls the minimum amount to bring it into view
            // block: 'start', // Scrolls to align the top of the item with the top of the scroll container
          });
        }
      }, 100); // Small delay
      return () => clearTimeout(timer);
    }
  }, [selectedStopData]); // Trigger effect when selectedStopData changes


  // --- Stop Click Handler ---
  const handleStopClick = useCallback(async (stopObject) => {
    const displayId = normalizeIdForDisplayAndCache(stopObject);
    const apiStopCode = stopObject.stop_code || displayId;
    const agency = stopObject.agency?.toLowerCase();

    const isCurrentlySelected = selectedStopData && normalizeIdForDisplayAndCache(selectedStopData) === displayId;

    // Update selected state
    setSelectedStopData(isCurrentlySelected ? null : stopObject); // Toggle selection
    setStopSchedule(null);
    setScheduleError(null);
    selectedItemRef.current = null; // Clear selected item ref initially

    if (isCurrentlySelected) {
      return; // If toggling off, just return
    }

    // If selecting a new stop
    setLoadingSchedule(true);

    const cached = getCachedSchedule(displayId);
    if (cached) {
      setStopSchedule(cached);
      setLoadingSchedule(false);
      return;
    }

    try {
      const predictionURL = (agency === "bart" || agency === "ba")
          ? `${baseApiUrl}/bart-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}`
          : `${baseApiUrl}/bus-positions/by-stop?stopCode=${apiStopCode}&agency=${agency}`;

      console.log(`[TransitInfo] Fetching schedule for ${displayId}`);
      const res = await axios.get(predictionURL, { timeout: API_TIMEOUT });
      const responseData = res.data?.realtime || res.data;

      // Use the combined processing function
      const schedule = await processAndGroupScheduleData(responseData, agency, baseApiUrl);

      setCachedSchedule(displayId, schedule);
      setStopSchedule(schedule);

    } catch (err) {
      console.error(`[TransitInfo] Failed fetch/process for ${displayId}:`, err);
      setScheduleError(`Failed to load schedule. ${err.message}`);
      setStopSchedule({ inbound: [], outbound: [] });
    } finally {
      setLoadingSchedule(false);
    }
  }, [selectedStopData, getCachedSchedule, setCachedSchedule, baseApiUrl]);

  // --- Refresh Handler ---
  const handleRefreshSchedule = useCallback(async () => {
        if (!selectedStopData) return;
        const displayId = normalizeIdForDisplayAndCache(selectedStopData);
        console.log(`[TransitInfo] Refresh triggered for ${displayId}`);
        delete SCHEDULE_CACHE[displayId]; // Clear cache
        // Find the full stop object again from stopsArray if needed, or use selectedStopData
        const currentStopObject = stopsArray.find(s => normalizeIdForDisplayAndCache(s) === displayId) || selectedStopData;
        if (currentStopObject) {
             await handleStopClick(currentStopObject); // Re-fetch
        }
    }, [selectedStopData, handleStopClick, stopsArray]);


  // --- Render Function for Route Groups ---
  const renderGroupedRouteInfo = (routeGroup) => {
        // ... (same rendering logic as previous response, displays "Vehicle near:") ...
        const predictionMinutes = routeGroup.predictions
                                   .map(p => p.minutes_until)
                                   .filter(mins => typeof mins === 'number' && !isNaN(mins));
        const predictionLabels = predictionMinutes.map(mins => getStatusChipInfo(mins).label);
        const firstPredictionMinutes = predictionMinutes[0];
        const chipInfoForFirst = getStatusChipInfo(firstPredictionMinutes);
        const nextArrivalTimeText = routeGroup.predictions[0]?.arrival_time_iso
                                    ? formatTime(routeGroup.predictions[0].arrival_time_iso)
                                    : (typeof firstPredictionMinutes === 'number' ? `in ${firstPredictionMinutes} min` : 'N/A');

        return (
            <Box className="route-info-box">
                <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={0.5}>
                    <Typography variant="h6" component="div" className="route-title" noWrap sx={{flexGrow: 1, mr: 1}}>
                        {renderRouteTypeIcon(routeGroup.route_number_display, routeGroup.agency)}
                        {routeGroup.route_number_display}
                        <Typography component="span" className="route-destination">
                            {' '}→ {routeGroup.destination}
                        </Typography>
                    </Typography>
                    <Chip
                        size="small"
                        label={predictionLabels.length > 0 ? predictionLabels.slice(0, 3).join(' / ') : "N/A"}
                        color={chipInfoForFirst.color}
                        sx={{ fontWeight: 'bold', fontSize: '0.75rem', flexShrink: 0 }}
                    />
                </Stack>
                <Typography variant="body2" className="route-arrival-detail">
                    Next at: {nextArrivalTimeText}
                </Typography>
                {/* Display Vehicle Location */}
                {routeGroup.vehicle_info?.nearest_stop ? (
                    <Typography variant="caption" className="route-vehicle-location">
                        Vehicle near: {routeGroup.vehicle_info.nearest_stop}
                    </Typography>
                ) : (predictionMinutes.length > 0) && ( // Show unavailable only if predictions exist
                     <Typography variant="caption" className="route-vehicle-location-unavailable">
                        Real-time vehicle location unavailable
                    </Typography>
                )}
            </Box>
        );
    };


  // --- Main Render ---
  return (
    <Card elevation={0} className="transit-card-custom">
      <CardContent sx={{ p: { xs: 1, sm: 1.5 } }}>
        <Typography className="transit-section-header" sx={{ pl: { xs: 0, sm: 1 } }}>
          Nearby Stops ({stopsArray.length})
        </Typography>

        {stopsArray.length === 0 && !loadingSchedule && ( <Typography align="center" color="text.secondary" sx={{ py: 3 }}> No stops found. </Typography> )}

        {/* Add ref to the List component */}
        <List ref={listRef} disablePadding className="nearby-stops-list">
          {stopsArray.map((stop) => {
            const uniqueKeyAndDisplayId = normalizeIdForDisplayAndCache(stop);
            const isSelected = selectedStopData && (normalizeIdForDisplayAndCache(selectedStopData) === uniqueKeyAndDisplayId);

            return (
              // Assign ref to the selected ListItem's container (Fragment or ListItem itself)
              <React.Fragment key={uniqueKeyAndDisplayId}>
                <ListItemButton
                  ref={isSelected ? selectedItemRef : null} // Assign ref ONLY if selected
                  onClick={() => handleStopClick(stop)}
                  sx={{ pt: 1, pb: 1, borderRadius: '4px', '&:hover': { backgroundColor: 'action.hover' }, mb: 0.5 }}
                  className={isSelected ? "stop-list-item stop-list-item-selected" : "stop-list-item"} // Add classes for potential styling
                >
                  {/* ... (ListItemButton content remains the same) ... */}
                  <Box flexGrow={1}>
                      <Stack direction="row" spacing={1} alignItems="center" mb={0.25}>
                          <LocationOnIcon color="primary" fontSize="small" />
                          <Typography fontWeight={500} noWrap sx={{ fontSize: '0.95rem' }}>
                              {stop.stop_name || 'Unknown Stop'}
                          </Typography>
                      </Stack>
                      <Stack direction="row" justifyContent="space-between" alignItems="center">
                          <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem' }}>
                              ID: {stop.stop_code || uniqueKeyAndDisplayId.replace(/-bart$/i, '').replace(/-muni$/i, '')}
                          </Typography>
                          {stop.distance_miles !== undefined && (
                              <Chip component="span" size="small" label={`${parseFloat(stop.distance_miles).toFixed(3)} mi`} sx={{ fontSize: '0.7rem', height: '18px', mr: 1 }} />
                          )}
                      </Stack>
                  </Box>
                  {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                </ListItemButton>

                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                   {/* Minimum height added to the Box inside Collapse */}
                  <Box
                    px={{ xs: 1, sm: 1.5 }} pb={1.5} pt={1}
                    sx={{
                        borderLeft: '3px solid var(--purpleLight)',
                        ml: { xs: 0.5, sm: 1 }, mr: { xs: 0.5, sm: 1 }, mb: 1,
                        minHeight: '150px' // ADD THIS: Set a minimum height for the details area
                    }}
                    className="stop-details-collapse" // Add class
                  >
                    <Button startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} disabled={loadingSchedule} size="small"
                      sx={{ mb: 1.5, textTransform: 'none', color: 'var(--purple)', '&:hover': { backgroundColor: 'var(--purpleLight)' } }}
                    >
                      {loadingSchedule && isSelected ? "Refreshing..." : "Refresh"}
                    </Button>

                    {loadingSchedule && isSelected && ( <Box py={3} display="flex" justifyContent="center"><CircularProgress size={28} /></Box> )}
                    {scheduleError && isSelected && ( <Alert severity="error" sx={{ fontSize: '0.85rem' }}>{scheduleError}</Alert> )}

                    {!loadingSchedule && !scheduleError && stopSchedule && isSelected && (
                      <>
                        {['inbound', 'outbound'].map((dirKey) => (
                          stopSchedule[dirKey] && Array.isArray(stopSchedule[dirKey]) && stopSchedule[dirKey].length > 0 && (
                            <Box key={dirKey} mb={2}>
                              <Typography variant="overline" display="block" gutterBottom sx={{ color: 'var(--current-grayMid-val)', fontSize: '0.7rem', fontWeight: 'bold' }}>
                                {dirKey.toUpperCase()}
                              </Typography>
                              <List dense disablePadding>
                                {stopSchedule[dirKey].map((routeGroup, i) => (
                                  <ListItem key={`${dirKey}-${routeGroup.route_number_display}-${routeGroup.destination}-${i}`} disablePadding className="transit-list-item-custom">
                                    <ListItemText primary={renderGroupedRouteInfo(routeGroup)} disableTypography />
                                  </ListItem>
                                ))}
                              </List>
                            </Box>
                          )
                        ))}
                        {(stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0) && (
                          <Typography className="transit-empty" sx={{ fontSize: '0.9rem', mt: 2 }}>No upcoming transit found.</Typography>
                        )}
                      </>
                    )}
                     {!loadingSchedule && !scheduleError && !stopSchedule && isSelected && ( <Typography variant="body2" color="text.secondary" sx={{mt:2}}>Schedule data unavailable.</Typography> )}
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