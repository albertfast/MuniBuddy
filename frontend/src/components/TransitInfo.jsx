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

const SCHEDULE_CACHE = {};
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const API_TIMEOUT = 15000; // 15 seconds timeout for API calls

// Helper to get a displayable stop ID (code, or part of gtfs_id)
const getDisplayableStopId = (stop) => {
    if (stop.stop_code_for_display) return stop.stop_code_for_display; // Preferred from App.jsx
    if (stop.stop_code) return stop.stop_code;
    if (stop.gtfs_stop_id) return stop.gtfs_stop_id.split('_').pop(); // Often the numerical part
    return 'N/A';
};


const formatTime = (isoTime) => {
    if (!isoTime || isoTime === "Unknown") return "Unknown";
    try {
        const date = new Date(isoTime);
        return isNaN(date.getTime()) ? isoTime : date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true, timeZone: 'America/Los_Angeles' });
    } catch { return isoTime; }
};

const renderRouteTypeIcon = (routeNumber, agency) => {
    const isBart = agency?.toLowerCase() === 'bart' || agency?.toLowerCase() === 'ba';
    // Heuristic: BART routes often are station names, Muni routes are numbers/letters
    const isLikelyTrain = isBart || (routeNumber && typeof routeNumber === 'string' && routeNumber.length > 3 && !/^\d+[A-Za-z]?$/.test(routeNumber));
    const IconComponent = isLikelyTrain ? TrainIcon : DirectionsBusIcon;
    return <IconComponent color="inherit" fontSize="small" sx={{ verticalAlign: 'middle', mr: 0.5 }} />;
};

const groupScheduleEntries = (entries = []) => {
  const groupedMap = new Map();
  for (const entry of entries) {
    const key = `${entry.route_number}__${entry.destination}`; // Group by route and destination
    if (!groupedMap.has(key)) {
      groupedMap.set(key, {
        route_number: entry.route_number,
        destination: entry.destination,
        arrivals_info: [], // Store full arrival details for better sorting/display
        is_realtime: entry.is_realtime,
        vehicle: entry.vehicle,
        earliest_arrival_time: entry.arrival_time, 
        earliest_minutes_until: entry.minutes_until,
      });
    }
    const currentGroup = groupedMap.get(key);
    currentGroup.arrivals_info.push({
        time: entry.arrival_time,
        minutes: entry.minutes_until,
        status: entry.status
    });
    // Update earliest arrival for the group
    if (entry.minutes_until !== null && (currentGroup.earliest_minutes_until === null || entry.minutes_until < currentGroup.earliest_minutes_until)) {
        currentGroup.earliest_minutes_until = entry.minutes_until;
        currentGroup.earliest_arrival_time = entry.arrival_time;
    }
    // Ensure is_realtime is true if any entry for this group is realtime
    if (entry.is_realtime) currentGroup.is_realtime = true;
  }
  
  // Sort arrivals within each group and format labels
  groupedMap.forEach(group => {
      group.arrivals_info.sort((a,b) => (a.minutes ?? Infinity) - (b.minutes ?? Infinity));
      group.arrival_labels = group.arrivals_info.map(arr => {
          if (arr.status === 'Due') return '[Due]';
          if (arr.minutes !== null) return `[${arr.minutes}${arr.minutes > 15 ? ' min' : ''}]`;
          return '[Scheduled]'; // Fallback for non-realtime with no minutes
      }).slice(0, 3); // Show up to 3 arrival times
  });

  return Array.from(groupedMap.values()).sort((a,b) => (a.earliest_minutes_until ?? Infinity) - (b.earliest_minutes_until ?? Infinity));
};
  
const getNearestStopName = async (lat, lon, baseApiUrl) => {
    if (!lat || !lon || !baseApiUrl) return ""; 
    try {
        const res = await axios.get(`${baseApiUrl}/nearby-stops`, { 
            params: { lat, lon, radius: 0.1, agency: 'muni' }, // Smaller radius for precision
            timeout: 4000 
        });
        const stops = res.data || [];
        // Prefer unique stop names, fall back to first if all are same
        const uniqueNames = [...new Set(stops.map(s => s.stop_name?.trim()).filter(Boolean))];
        return uniqueNames[0] || stops[0]?.stop_name?.trim() || "";
    } catch (err) {
        // console.warn('[nearestStopName] Error:', err.message);
        return ""; 
    }
};

const normalizeSiriData = async (visits = [], baseApiUrl) => {
    const processedEntries = [];
    for (const visit of visits) {
        const journey = visit?.MonitoredVehicleJourney; if (!journey) continue;
        const call = journey?.MonitoredCall || {};
        const directionRef = (journey?.DirectionRef || "0").toLowerCase();
        const arrivalTimeISO = call?.ExpectedArrivalTime || call?.AimedArrivalTime;
        const arrivalDate = arrivalTimeISO ? new Date(arrivalTimeISO) : null;
        const now = new Date();
        const minutesUntil = arrivalDate ? Math.max(0, Math.round((arrivalDate - now) / 60000)) : null;
        
        // Fetch nearest stop name only if lat/lon are valid
        let nearestStop = "";
        if (journey?.VehicleLocation?.Latitude && journey?.VehicleLocation?.Longitude) {
            nearestStop = await getNearestStopName(journey.VehicleLocation.Latitude, journey.VehicleLocation.Longitude, baseApiUrl);
        }

        const entry = {
            route_number: journey?.LineRef ? `${journey.LineRef} ${journey?.PublishedLineName ?? ''}`.trim() : journey?.PublishedLineName ?? "Unknown Line",
            destination: call?.DestinationDisplay || journey?.DestinationName || "Unknown Dest.",
            arrival_time: arrivalTimeISO || "Unknown",
            status: minutesUntil !== null ? (minutesUntil === 0 ? "Due" : `${minutesUntil} min`) : "Unknown",
            minutes_until: minutesUntil,
            is_realtime: !!call?.ExpectedArrivalTime, // True if ExpectedArrivalTime exists
            vehicle: { 
                lat: journey?.VehicleLocation?.Latitude || "", 
                lon: journey?.VehicleLocation?.Longitude || "", 
                nearest_stop: nearestStop 
            },
            direction_key: (directionRef === "0" || directionRef === "inbound" || journey?.DirectionName?.toLowerCase().includes("inbound")) ? 'inbound' : 'outbound'
        };
        processedEntries.push(entry);
    }
    // Grouping will happen after all entries are processed
    const grouped = { inbound: [], outbound: [] };
    processedEntries.forEach(entry => grouped[entry.direction_key].push(entry));
    
    grouped.inbound.sort((a,b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
    grouped.outbound.sort((a,b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
    return grouped;
};

const adaptBartData = (bartData) => {
     const adapted = { inbound: [], outbound: [] };
     if (!bartData || (!bartData.inbound && !bartData.outbound)) return adapted; // Check if either exists
     
     for (const dir of ['inbound', 'outbound']) {
         if (Array.isArray(bartData[dir])) {
             adapted[dir] = bartData[dir].map(bartRoute => {
                 const minutesUntil = typeof bartRoute.minutes_until === 'number' ? bartRoute.minutes_until : parseInt(bartRoute.arrival_time, 10);
                 if (isNaN(minutesUntil)) return null; // Skip if minutes_until is not a number
                 return {
                     route_number: bartRoute.route_number || "BART",
                     destination: bartRoute.destination || "Unknown BART Dest.",
                     arrival_time: null, // BART API might not provide ISO time in this format
                     status: minutesUntil === 0 ? "Due" : `${minutesUntil} min`,
                     minutes_until: minutesUntil,
                     is_realtime: true, // BART data is generally realtime
                     vehicle: { nearest_stop: "" } // BART vehicle location not typically in this API response
                 };
             }).filter(Boolean); // Remove null entries
             adapted[dir].sort((a, b) => (a.minutes_until ?? Infinity) - (b.minutes_until ?? Infinity));
         }
     }
     return adapted;
};

const TransitInfo = ({ stops, baseApiUrl /* setLiveVehicleMarkers removed for now */ }) => {
    const [selectedStopId, setSelectedStopId] = useState(null); // Stores stop.display_id_for_transit_info
    const [selectedStopObject, setSelectedStopObject] = useState(null);
    const [stopSchedule, setStopSchedule] = useState(null);
    const [loadingSchedule, setLoadingSchedule] = useState(false);
    const [scheduleError, setScheduleError] = useState(null);
    
    const listRef = useRef(null);
    const selectedItemRef = useRef(null);

    const stopsArray = useMemo(() => Object.values(stops || {}), [stops]);

    const getCachedSchedule = useCallback((stopId) => {
        const item = SCHEDULE_CACHE[stopId];
        return item && (Date.now() - item.timestamp < CACHE_TTL) ? item.data : null;
    }, []);
    const setCachedSchedule = useCallback((stopId, data) => {
        SCHEDULE_CACHE[stopId] = { data, timestamp: Date.now() };
    }, []);

    useEffect(() => {
        if (selectedItemRef.current && listRef.current) {
            const timer = setTimeout(() => {
                selectedItemRef.current?.scrollIntoView({
                    behavior: 'smooth',
                    block: window.innerWidth < 600 ? 'start' : 'nearest', // More specific block for mobile
                });
            }, 150); // Slightly longer delay for layout to settle
            return () => clearTimeout(timer);
        }
    }, [selectedStopId]);

    const handleStopClick = useCallback(async (stopObject, forceRefresh = false) => {
        const currentStopApiId = stopObject.display_id_for_transit_info || getDisplayableStopId(stopObject); // Use ID from App.jsx
        
        if (!currentStopApiId) {
            console.warn("Stop clicked without a valid API identifier:", stopObject);
            setScheduleError("Cannot fetch schedule for this stop (missing ID).");
            return;
        }
        
        selectedItemRef.current = null; // Reset ref before new selection

        if (currentStopApiId === selectedStopId && !forceRefresh) {
            setSelectedStopId(null); setSelectedStopObject(null); setStopSchedule(null); setScheduleError(null);
            return;
        }

        setSelectedStopId(currentStopApiId);
        setSelectedStopObject(stopObject);
        setStopSchedule(null); setScheduleError(null); setLoadingSchedule(true);

        const cached = getCachedSchedule(currentStopApiId);
        if (cached && !forceRefresh) {
            setStopSchedule(cached); setLoadingSchedule(false); return;
        }

        try {
            const agency = stopObject.agency?.toLowerCase();
            const predictionURL = (agency === "bart" || agency === "ba")
                ? `${baseApiUrl}/bart-positions/by-stop?stopCode=${currentStopApiId}&agency=${agency}`
                : `${baseApiUrl}/bus-positions/by-stop?stopCode=${currentStopApiId}&agency=${agency}`;

            const res = await axios.get(predictionURL, { timeout: API_TIMEOUT });
            const responseData = res.data?.realtime || res.data; // Prefer 'realtime' key if exists
            const siriVisits = responseData?.ServiceDelivery?.StopMonitoringDelivery?.MonitoredStopVisit;

            let scheduleData;
            if (Array.isArray(siriVisits)) {
                const normalized = await normalizeSiriData(siriVisits, baseApiUrl);
                scheduleData = {
                    inbound: groupScheduleEntries(normalized.inbound),
                    outbound: groupScheduleEntries(normalized.outbound)
                };
            } else if ((agency === "bart" || agency === "ba") && responseData && (responseData.inbound || responseData.outbound)) {
                scheduleData = adaptBartData(responseData); // Use adapted BART data
                 scheduleData = { // BART data might already be grouped like this from backend
                    inbound: groupScheduleEntries(scheduleData.inbound),
                    outbound: groupScheduleEntries(scheduleData.outbound)
                };
            } else {
                scheduleData = { inbound: [], outbound: [] };
                if (responseData && Object.keys(responseData).length > 0) { // If there's data but not processable
                    setScheduleError('Schedule format not recognized.');
                } else { // No data at all
                    setScheduleError('No schedule data received for this stop.');
                }
            }
            
            setCachedSchedule(currentStopApiId, scheduleData);
            setStopSchedule(scheduleData);

        } catch (err) {
            console.error(`[TransitInfo] Schedule fetch error for ${currentStopApiId}:`, err);
            let errorMsg = "Failed to load schedule.";
            if (err.response) errorMsg += ` Server responded with ${err.response.status}.`;
            else if (err.request) errorMsg += " No response from server.";
            else errorMsg += ` ${err.message}`;
            setScheduleError(errorMsg);
            setStopSchedule({ inbound: [], outbound: [] });
        } finally {
            setLoadingSchedule(false);
        }
    }, [selectedStopId, baseApiUrl, getCachedSchedule, setCachedSchedule]);

    const handleRefreshSchedule = useCallback(() => {
        if (!selectedStopId || !selectedStopObject) return;
        // No need to delete from SCHEDULE_CACHE here, handleStopClick with forceRefresh will bypass it
        handleStopClick(selectedStopObject, true);
    }, [selectedStopId, selectedStopObject, handleStopClick]);

    const renderRouteInfo = useCallback((routeEntry) => {
      const agency = selectedStopObject?.agency;
      return (
        <Box className="route-info-box">
          <Stack direction="row" justifyContent="space-between" alignItems="center" spacing={1} mb={0.5}>
            <Typography variant="body1" component="div" className="route-title" noWrap sx={{ flexGrow: 1, mr: 1 }}>
              {renderRouteTypeIcon(routeEntry.route_number, agency)}
              {routeEntry.route_number || "Route ?"}
              <Typography component="span" className="route-destination">
                → {routeEntry.destination || "Unknown Destination"}
              </Typography>
            </Typography>
             {routeEntry.is_realtime && <Chip label="Live" size="small" color="success" sx={{height: '18px', fontSize:'0.65rem', backgroundColor: 'var(--greenDark)', color:'white'}}/>}
          </Stack>
    
          {routeEntry.earliest_arrival_time && routeEntry.earliest_arrival_time !== "Unknown" && (
            <Typography variant="body2" className="route-arrival-detail">
              Next: <b>{formatTime(routeEntry.earliest_arrival_time)}</b>
              {routeEntry.earliest_minutes_until !== null && ` (${routeEntry.earliest_minutes_until === 0 ? "Due" : `${routeEntry.earliest_minutes_until} min`})`}
            </Typography>
          )}
          
          {routeEntry.arrival_labels && routeEntry.arrival_labels.length > 0 && (
            <Stack direction="row" spacing={0.5} mt={0.5} flexWrap="wrap">
                {routeEntry.arrival_labels.map((label, i) => {
                    let chipColor = "default";
                    const cleanLabel = label.replace(/\[|\]/g, '').replace(' min', '');
                    const minutes = parseInt(cleanLabel);
                    if (label === "[Due]") chipColor = "error";
                    else if (!isNaN(minutes)) {
                        if (minutes <= 5) chipColor = "success";
                        else if (minutes <= 15) chipColor = "warning";
                    }
                    return <Chip key={i} size="small" label={cleanLabel + (label.includes('min') ? " min" : "")} color={chipColor} />;
                })}
            </Stack>
          )}

          {routeEntry.vehicle?.nearest_stop && (
            <Typography variant="caption" className="route-vehicle-location" sx={{ mt: 0.5, display: 'block' }}>
              Vehicle near: {routeEntry.vehicle.nearest_stop}
            </Typography>
          )}
        </Box>
      );
    }, [selectedStopObject]);

    return (
        <Card elevation={0} className="transit-card-custom">
            <CardContent>
                 <Typography className="transit-section-header"> Nearby Stops ({stopsArray.length}) </Typography>
                 {stopsArray.length === 0 && !loadingSchedule && (
                    <Typography className="transit-empty"> No stops found. Adjust search or radius. </Typography>
                 )}

                <List ref={listRef} dense disablePadding className="nearby-stops-list">
                    {stopsArray.map((stop) => {
                        const stopApiId = stop.display_id_for_transit_info || getDisplayableStopId(stop);
                        const reactKey = stop.original_stop_id_for_key || stopApiId || stop.stop_name; // Ensure unique key
                        const isSelected = stopApiId === selectedStopId;

                        return (
                            <React.Fragment key={reactKey}>
                                <ListItemButton 
                                    ref={isSelected ? selectedItemRef : null} 
                                    onClick={() => handleStopClick(stop)}
                                    selected={isSelected}
                                    sx={{ mb: 0.5 }}
                                >
                                    <Box flexGrow={1} overflow="hidden">
                                        <Stack direction="row" spacing={1} alignItems="center" mb={0.25}>
                                            <LocationOnIcon color={isSelected ? "primary" : "action"} fontSize="small" />
                                            <Typography fontWeight={500} noWrap sx={{ fontSize: '0.95rem' }}>
                                                {stop.stop_name || 'Unknown Stop Name'}
                                            </Typography>
                                        </Stack>
                                        <Stack direction="row" justifyContent="space-between" alignItems="center">
                                            <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.75rem', ml: 3.5 /* Align with icon */ }}>
                                                ID: {getDisplayableStopId(stop)} {stop.agency && `(${stop.agency.toUpperCase()})`}
                                            </Typography>
                                            {stop.distance_miles != null && (
                                                <Chip component="span" size="small" label={`${Number(stop.distance_miles).toFixed(2)} mi`} sx={{ fontSize: '0.7rem', height: '18px' }} />
                                            )}
                                        </Stack>
                                    </Box>
                                    {isSelected ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                                </ListItemButton>

                                <Collapse in={isSelected} timeout="auto" unmountOnExit>
                                    <Box role="region" sx={{ px: { xs: 0.5, sm: 1 }, pb: 1.5, pt: 1, borderLeft: '3px solid var(--purpleMid)', ml: 1, mr: 0.5, mb: 1, minHeight: '120px', display: 'flex', flexDirection: 'column' }}>
                                        <Button size="small" variant="outlined" startIcon={<RefreshIcon />} onClick={handleRefreshSchedule} sx={{ mb: 1, alignSelf: 'flex-start' }} disabled={loadingSchedule}>
                                            {loadingSchedule && isSelected ? "Refreshing..." : "Refresh Times"}
                                        </Button>
                                        {loadingSchedule && isSelected ? ( /* Show loader only if this stop is loading */
                                            <Box sx={{ flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '80px' }}><CircularProgress size={28} /></Box>
                                        ) : scheduleError && isSelected ? (
                                            <Alert severity="warning" sx={{ fontSize: '0.8rem' }}>{scheduleError}</Alert>
                                        ) : stopSchedule && isSelected ? (
                                            <>
                                                {['inbound', 'outbound'].map((dir) => (
                                                    stopSchedule[dir]?.length > 0 && (
                                                        <Box key={dir} mb={1.5}>
                                                            <Typography variant="overline" display="block" gutterBottom>{dir}</Typography>
                                                            <List dense disablePadding>
                                                                {stopSchedule[dir].map((routeEntry, i) => (
                                                                    <ListItem key={`${dir}-${routeEntry.route_number}-${routeEntry.destination}-${i}`} disablePadding sx={{mb: 0.5}} className="transit-list-item-custom">
                                                                        <ListItemText primary={renderRouteInfo(routeEntry)} disableTypography />
                                                                    </ListItem>
                                                                ))}
                                                            </List>
                                                        </Box>
                                                    )
                                                ))}
                                                {(stopSchedule.inbound?.length === 0 && stopSchedule.outbound?.length === 0) && !scheduleError && (
                                                    <Typography className="transit-empty" sx={{mt:1}}>No upcoming departures found for this stop.</Typography>
                                                )}
                                            </>
                                        ) : isSelected && !scheduleError ? ( // Selected, not loading, no error, but no schedule (could be initial state)
                                            <Typography className="transit-empty" sx={{mt:1}}>Select a stop to see schedule.</Typography>
                                        ) : null}
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

export default React.memo(TransitInfo);