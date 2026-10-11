import React, { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'

function GeoMap({ points }) {
  const mapRef = useRef(null)
  const mapCenter = [20, 0]
  const mapZoom = 1.6

  useEffect(() => {
    if (!mapRef.current) return
    const timer = window.setTimeout(() => {
      mapRef.current.invalidateSize()
    }, 120)
    return () => window.clearTimeout(timer)
  }, [points.length])

  return (
    <MapContainer
      center={mapCenter}
      zoom={mapZoom}
      scrollWheelZoom
      className="geo-leaflet"
      style={{ height: '100%', width: '100%' }}
      whenCreated={(map) => {
        mapRef.current = map
      }}
    >
      <TileLayer
        attribution="© OpenStreetMap contributors © CARTO"
        url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
      />
      {points.map((point) => (
        <CircleMarker
          key={`${point.city}-${point.country}`}
          center={[point.lat, point.lng]}
          radius={6 + Math.min(point.count, 6)}
          pathOptions={{ color: '#38bdf8', fillColor: '#38bdf8', fillOpacity: 0.8 }}
        >
          <Tooltip direction="top" offset={[0, -6]} opacity={1}>
            {point.city}, {point.country} · {point.count}
          </Tooltip>
        </CircleMarker>
      ))}
    </MapContainer>
  )
}

export default GeoMap
