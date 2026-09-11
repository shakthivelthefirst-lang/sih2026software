import React, { useEffect, useRef } from "react";
import { MapContainer, TileLayer, GeoJSON, Marker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useData, Panel } from "./App";

export function isParcelAcquired(parcel) {
  if (!parcel) return false;

  const stage = String(parcel.stage ?? "").trim().toUpperCase();
  const acqStatus = String(parcel.acquisition_status ?? "").trim().toUpperCase();
  const rawStatus = String(parcel.raw_status ?? parcel.normalized_status ?? parcel.status ?? "").trim().toUpperCase();

  // Negative checks: If stage or status is NOT ACQUIRED, pending, proposal, etc., it MUST evaluate to NOT ACQUIRED
  const notAcquiredValues = [
    "NOT ACQUIRED",
    "NOT_ACQUIRED",
    "PENDING",
    "PROPOSAL",
    "IN PROGRESS",
    "IN_PROGRESS",
    "SIA / SURVEY",
    "SURVEY",
    "NOTIFICATION",
    "OBJECTIONS",
    "APPROVAL",
    "AWARD"
  ];

  if (notAcquiredValues.includes(stage) || stage.includes("NOT ACQUIRED") || stage.includes("PENDING")) {
    return false;
  }
  if (notAcquiredValues.includes(acqStatus) || acqStatus.includes("NOT ACQUIRED") || acqStatus.includes("PENDING")) {
    return false;
  }
  if (notAcquiredValues.includes(rawStatus) || rawStatus.includes("NOT ACQUIRED") || rawStatus.includes("PENDING")) {
    return false;
  }

  // Boolean / numeric flags
  if (parcel.is_acquired === false || parcel.is_acquired === 0 || parcel.is_acquired === "0") return false;
  if (parcel.acquired === false || parcel.acquired === 0 || parcel.acquired === "0") return false;
  if (parcel.is_acquired === true || parcel.is_acquired === 1 || parcel.is_acquired === "1") return true;
  if (parcel.acquired === true || parcel.acquired === 1 || parcel.acquired === "1") return true;

  const acquiredValues = [
    "ACQUIRED",
    "COMPLETED",
    "AWARD_PASSED",
    "POSSESSION_TAKEN",
    "POSSESSION",
    "CLOSED",
    "ON TRACK",
    "PAID",
    "VERIFIED"
  ];

  if (acquiredValues.includes(stage)) return true;
  if (acquiredValues.includes(acqStatus)) return true;
  if (acquiredValues.includes(rawStatus)) return true;

  return false;
}

export const createSquareIcon = (isAcquired) => L.divIcon({
  className: "custom-parcel-icon",
  html: `<div class="parcel-square ${isAcquired ? "acquired" : "not-acquired"}"></div>`,
  iconSize: [12, 12],
  iconAnchor: [6, 6],
  popupAnchor: [0, -8]
});

// Zonal styling based on acquisition status
export const getParcelStyle = (feature) => {
  const acquired = isParcelAcquired(feature.properties);
  return {
    fillColor: acquired ? "#22c55e" : "#ef4444",
    weight: 1.5,
    opacity: 1,
    color: acquired ? "#15803d" : "#b91c1c",
    fillOpacity: 0.5
  };
};

export const onEachFeature = (feature, layer) => {
  const props = feature.properties || {};
  const acquired = isParcelAcquired(props);
  const statusDisplay = acquired ? "ACQUIRED" : "NOT ACQUIRED";
  const surveyNo = props.survey_no || props.survey_number || "N/A";
  const area = props.area || "N/A";
  const locality = props.locality || props.specific_area || props.revenue_village || props.village || "N/A";

  // Tooltip showing Survey No, Area, Locality, and Status
  const tooltipContent = `
    <div style="font-size: 11px; line-height: 1.4; font-family: sans-serif;">
      <div><b>Survey No:</b> ${surveyNo}</div>
      <div><b>Area:</b> ${area}</div>
      <div><b>Locality:</b> ${locality}</div>
      <div><b>Status:</b> <span style="font-weight: bold; color: ${acquired ? "#15803d" : "#b91c1c"};">${statusDisplay}</span></div>
    </div>
  `;
  layer.bindTooltip(tooltipContent, { sticky: true });

  // Popup showing Survey No, Area, Locality, and Status
  const popupContent = `
    <div style="font-size: 12px; line-height: 1.6; min-width: 170px; font-family: sans-serif;">
      <div style="font-weight: bold; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; margin-bottom: 6px;">
        Survey No: ${surveyNo}
      </div>
      <div><b>Parcel ID:</b> ${props.parcel_id || feature.id || "N/A"}</div>
      <div><b>Area:</b> ${area}</div>
      <div><b>Locality:</b> ${locality}</div>
      <div style="margin-top: 6px;">
        <b>Status:</b>
        <span style="font-weight: bold; color: ${acquired ? "#15803d" : "#b91c1c"}; padding: 2px 6px; border-radius: 3px; font-size: 11px; background: ${acquired ? "#dcfce7" : "#fee2e2"}; display: inline-block;">
          ${statusDisplay}
        </span>
      </div>
    </div>
  `;
  layer.bindPopup(popupContent);

  // Hover highlight: increase weight to 3 and fillOpacity to 0.75 on mouseover
  layer.on({
    mouseover: (e) => {
      const target = e.target;
      target.setStyle({
        weight: 3,
        fillOpacity: 0.75
      });
      if (!L.Browser.ie && !L.Browser.opera && !L.Browser.edge) {
        target.bringToFront();
      }
    },
    mouseout: (e) => {
      const target = e.target;
      target.setStyle(getParcelStyle(feature));
    }
  });
};

function GeoJsonLayerWithBounds({ featureCollection, projectId }) {
  const map = useMap();
  const geojsonRef = useRef(null);

  const fit = (layer) => {
    if (!map || !layer) return;
    try {
      map.invalidateSize();
      if (typeof layer.getBounds === "function") {
        const bounds = layer.getBounds();
        if (bounds && bounds.isValid()) {
          map.fitBounds(bounds, { padding: [40, 40], maxZoom: 16 });
        }
      }
    } catch (err) {
      console.warn("map.fitBounds(geojsonLayer.getBounds()) failed:", err);
    }
  };

  useEffect(() => {
    if (!map) return;
    const timer = setTimeout(() => {
      if (geojsonRef.current) {
        fit(geojsonRef.current);
      }
    }, 50);
    return () => clearTimeout(timer);
  }, [map, featureCollection, projectId]);

  return (
    <GeoJSON
      key={`geojson-${projectId}-${featureCollection.features.length}`}
      ref={(layer) => {
        geojsonRef.current = layer;
        if (layer) fit(layer);
      }}
      data={featureCollection}
      style={getParcelStyle}
      onEachFeature={onEachFeature}
    />
  );
}

export default function ProjectAcquisitionMap({ projectId }) {
  const { data, error } = useData(projectId ? `/projects/${encodeURIComponent(projectId)}/parcels` : null, 5000);

  if (error) {
    return (
      <Panel title="Project Acquisition Map">
        <div className="error">Unable to load project acquisition map: {error.message}</div>
      </Panel>
    );
  }

  if (!data) {
    return (
      <Panel title="Project Acquisition Map">
        <p>Loading project acquisition map...</p>
      </Panel>
    );
  }

  // 1. Isolate parcels to currently opened project
  const allParcels = Array.isArray(data)
    ? data
    : (data?.features || data?.parcels || []);

  const isolatedParcels = allParcels.filter(p => {
    if (!p) return false;
    const pid = p.project_id || p.properties?.project_id;
    return !pid || String(pid).trim() === String(projectId).trim();
  });

  // 2. Convert parcel data into GeoJSON Features if not already formatted as FeatureCollection
  const featureCollection = {
    type: "FeatureCollection",
    features: isolatedParcels.map((p, idx) => {
      if (p.type === "Feature" && p.geometry) {
        const props = p.properties || {};
        return {
          ...p,
          properties: {
            ...props,
            ...p,
            parcel_id: props.parcel_id || p.parcel_id || p.id || idx,
            survey_no: props.survey_no || p.survey_no || "N/A",
            area: props.area || (p.area ? `${p.area} ${p.area_unit || "acres"}` : "N/A"),
            locality: props.locality || props.specific_area || p.specific_area || props.village || p.village || "N/A",
            stage: props.stage || p.stage || p.acquisition_status || "NOT ACQUIRED",
            acquisition_status: props.acquisition_status || p.acquisition_status || "NOT ACQUIRED",
            is_acquired: props.is_acquired ?? p.is_acquired,
            latitude: Number(props.latitude ?? p.latitude),
            longitude: Number(props.longitude ?? p.longitude),
            project_id: props.project_id || p.project_id || projectId
          }
        };
      }

      const lat = Number(p.latitude);
      const lon = Number(p.longitude);
      let geometry = p.geometry;

      if (!geometry || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) {
        if (!isNaN(lat) && !isNaN(lon) && isFinite(lat) && isFinite(lon)) {
          const areaVal = parseFloat(p.area || 1.0);
          const side_m = Math.sqrt(Math.max(areaVal, 0.1) * 4046.86);
          const d_lat = Math.max(Math.min((side_m / 111000.0) / 2.0, 0.003), 0.0003);
          const d_lon = Math.max(Math.min((side_m / (111000.0 * Math.max(Math.cos(lat * Math.PI / 180), 0.1))) / 2.0, 0.003), 0.0003);
          geometry = {
            type: "Polygon",
            coordinates: [[
              [Number((lon - d_lon).toFixed(6)), Number((lat - d_lat).toFixed(6))],
              [Number((lon + d_lon).toFixed(6)), Number((lat - d_lat).toFixed(6))],
              [Number((lon + d_lon).toFixed(6)), Number((lat + d_lat).toFixed(6))],
              [Number((lon - d_lon).toFixed(6)), Number((lat + d_lat).toFixed(6))],
              [Number((lon - d_lon).toFixed(6)), Number((lat - d_lat).toFixed(6))]
            ]]
          };
        }
      }

      return {
        type: "Feature",
        id: p.parcel_id || p.id || idx,
        geometry: geometry,
        properties: {
          ...p,
          parcel_id: p.parcel_id || p.id || idx,
          survey_no: p.survey_no || p.survey_number || "N/A",
          area: p.area ? `${p.area} ${p.area_unit || "acres"}` : "N/A",
          locality: p.locality || p.specific_area || p.revenue_village || p.village || "N/A",
          village: p.village || "N/A",
          stage: p.stage || p.acquisition_status || "NOT ACQUIRED",
          acquisition_status: p.acquisition_status || p.stage || "NOT ACQUIRED",
          is_acquired: p.is_acquired,
          latitude: lat,
          longitude: lon,
          project_id: p.project_id || projectId
        }
      };
    }).filter(f => f.geometry && (f.geometry.type === "Polygon" || f.geometry.type === "MultiPolygon" || f.geometry.type === "Point"))
  };

  const totalParcels = featureCollection.features.length;
  const acquiredParcels = featureCollection.features.filter(f => isParcelAcquired(f.properties)).length;
  const notAcquiredParcels = totalParcels - acquiredParcels;
  const rawProgress = totalParcels > 0 ? (acquiredParcels / totalParcels) * 100 : 0;
  const progress = Number.isInteger(rawProgress) ? rawProgress : Math.round(rawProgress * 10) / 10;

  const defaultCenter = featureCollection.features.length > 0 && featureCollection.features[0].properties.latitude
    ? [featureCollection.features[0].properties.latitude, featureCollection.features[0].properties.longitude]
    : [11.0168, 76.9558];

  return (
    <Panel title="Project Acquisition Map">
      <div className="project-map-header">
        <div className="project-map-metrics">
          <div className="project-map-pill">
            <span>Total Parcels:</span> <b>{totalParcels}</b>
          </div>
          <div className="project-map-pill">
            <span className="legend-square acquired" style={{ width: "10px", height: "10px", marginRight: "2px" }}></span>
            <span>Acquired:</span> <b style={{ color: "#16a34a" }}>{acquiredParcels}</b>
          </div>
          <div className="project-map-pill">
            <span className="legend-square not-acquired" style={{ width: "10px", height: "10px", marginRight: "2px" }}></span>
            <span>Not Acquired:</span> <b style={{ color: "#dc2626" }}>{notAcquiredParcels}</b>
          </div>
          <div className="project-map-pill">
            <span>Acquisition Progress:</span> <b>{progress}%</b>
          </div>
        </div>

        <div className="project-map-legend" aria-label="Acquisition Map Legend">
          <span className="legend-item" title="■ Acquired (Green square)">
            <span className="legend-square acquired"></span>
            <span>■ Acquired</span>
          </span>
          <span className="legend-item" title="■ Not Acquired (Red square)">
            <span className="legend-square not-acquired"></span>
            <span>■ Not Acquired</span>
          </span>
        </div>
      </div>

      {featureCollection.features.length === 0 ? (
        <div className="empty">No mapped parcels found for this project.</div>
      ) : (
        <div className="map" style={{ height: "460px" }}>
          <MapContainer key={projectId} center={defaultCenter} zoom={12} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {/* GeoJSON layer with zonal styling, hover highlight, and automatic fitBounds */}
            <GeoJsonLayerWithBounds featureCollection={featureCollection} projectId={projectId} />

            {/* Square block markers centered at parcel coordinates */}
            {featureCollection.features.map((f) => {
              const lat = f.properties?.latitude;
              const lon = f.properties?.longitude;
              if (lat == null || lon == null || isNaN(Number(lat)) || isNaN(Number(lon))) return null;
              const isAcq = isParcelAcquired(f.properties);
              const surveyNo = f.properties?.survey_no || "N/A";
              const parcelId = f.properties?.parcel_id || f.id || "N/A";
              const area = f.properties?.area || "N/A";
              const locality = f.properties?.locality || f.properties?.village || "N/A";
              const statusDisplay = isAcq ? "ACQUIRED" : "NOT ACQUIRED";

              return (
                <Marker
                  key={`marker-${parcelId}-${lat}-${lon}`}
                  position={[Number(lat), Number(lon)]}
                  icon={createSquareIcon(isAcq)}
                >
                  <Popup>
                    <div style={{ fontSize: "12px", lineHeight: "1.6", minWidth: "170px" }}>
                      <div style={{ fontWeight: "bold", borderBottom: "1px solid #e2e8f0", paddingBottom: "4px", marginBottom: "6px" }}>
                        Survey No: {surveyNo}
                      </div>
                      <div><b>Parcel ID:</b> {parcelId}</div>
                      <div><b>Area:</b> {area}</div>
                      <div><b>Locality:</b> {locality}</div>
                      <div style={{ marginTop: "6px" }}>
                        <b>Status:</b>{" "}
                        <span style={{
                          fontWeight: "bold",
                          color: isAcq ? "#15803d" : "#b91c1c",
                          padding: "2px 6px",
                          borderRadius: "3px",
                          fontSize: "11px",
                          background: isAcq ? "#dcfce7" : "#fee2e2",
                          display: "inline-block"
                        }}>
                          {statusDisplay}
                        </span>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </MapContainer>
        </div>
      )}
      <small style={{ color: "#64748b", display: "block", marginTop: "8px" }}>
        Showing {featureCollection.features.length} mapped parcel{featureCollection.features.length === 1 ? "" : "s"} for project {projectId}. Zonal boundaries: 🟩 Green (#22c55e) = Acquired, 🟥 Red (#ef4444) = Not Acquired.
      </small>
    </Panel>
  );
}
