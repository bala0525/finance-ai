import React from "react";
import "./Loader.css";

export function SkeletonBlock({ className = "", style = {}, rounded = false }) {
  return <span aria-hidden="true" className={`skeleton-block ${rounded ? "skeleton-rounded" : ""} ${className}`} style={style} />;
}

export function SkeletonLoader({ variant = "workspace", rows = 5 }) {
  if (variant === "cards") {
    return (
      <div className="skeleton-card-grid" role="status" aria-label="Loading content">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="skeleton-card" key={index}>
            <SkeletonBlock style={{ width: "42%", height: 10 }} />
            <SkeletonBlock style={{ width: "58%", height: 27, marginTop: 16 }} />
            <SkeletonBlock style={{ width: "72%", height: 9, marginTop: 12 }} />
          </div>
        ))}
      </div>
    );
  }
  if (variant === "table") {
    return (
      <div className="skeleton-table" role="status" aria-label="Loading table">
        <div className="skeleton-table-row skeleton-table-head">
          {Array.from({ length: 5 }).map((_, index) => <SkeletonBlock key={index} style={{ width: `${18 + (index % 2) * 8}%`, height: 9 }} />)}
        </div>
        {Array.from({ length: rows }).map((_, row) => (
          <div className="skeleton-table-row" key={row}>
            {Array.from({ length: 5 }).map((__, col) => <SkeletonBlock key={col} style={{ width: `${col === 0 ? 70 : 45 + ((row + col) % 3) * 12}%`, height: 11 }} />)}
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="skeleton-workspace" role="status" aria-label="Loading workspace">
      <SkeletonBlock style={{ width: "34%", height: 20 }} />
      <SkeletonBlock style={{ width: "58%", height: 10, marginTop: 10 }} />
      <SkeletonLoader variant="cards" />
      <SkeletonLoader variant="table" rows={rows} />
    </div>
  );
}

export default function Loader({ label = "Loading..." }) {
  return <div className="app-loading" role="status"><span className="app-loading-dot" /><span>{label}</span></div>;
}
