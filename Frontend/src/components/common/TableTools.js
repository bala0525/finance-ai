import { useMemo, useState } from "react";

/*
 * Shared client-side search + sort for the AI employee workspaces.
 *   sorts: [{ key, label, get: (row) => comparable }]
 */
export function useSearchSort(rows, { searchText, sorts, defaultSort }) {
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState(defaultSort?.key || sorts[0]?.key);
  const [direction, setDirection] = useState(defaultSort?.direction || "desc");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const source = Array.isArray(rows) ? rows : [];
    const matches = needle
      ? source.filter((row) => searchText(row).toLowerCase().includes(needle))
      : source.slice();

    const sorter = sorts.find((item) => item.key === sortKey);
    if (!sorter) return matches;

    const factor = direction === "asc" ? 1 : -1;
    return matches.sort((a, b) => {
      const left = sorter.get(a);
      const right = sorter.get(b);
      const leftEmpty = left === null || left === undefined || left === "";
      const rightEmpty = right === null || right === undefined || right === "";
      if (leftEmpty && rightEmpty) return 0;
      if (leftEmpty) return 1; // empty values always last
      if (rightEmpty) return -1;
      if (typeof left === "number" && typeof right === "number") {
        return (left - right) * factor;
      }
      return String(left).localeCompare(String(right), undefined, { numeric: true, sensitivity: "base" }) * factor;
    });
  }, [rows, query, sortKey, direction, searchText, sorts]);

  return {
    query,
    setQuery,
    sortKey,
    setSortKey,
    direction,
    toggleDirection: () => setDirection((d) => (d === "asc" ? "desc" : "asc")),
    filtered,
    total: Array.isArray(rows) ? rows.length : 0,
    sorts,
  };
}

export function TableToolbar({ controls, placeholder = "Search...", label = "items" }) {
  return (
    <div className="workspace-toolbar">
      <input
        type="search"
        className="workspace-search"
        value={controls.query}
        onChange={(event) => controls.setQuery(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
      />
      <label className="workspace-sort">
        <span>Sort by</span>
        <select
          value={controls.sortKey}
          onChange={(event) => controls.setSortKey(event.target.value)}
          aria-label="Sort by"
        >
          {controls.sorts.map((item) => (
            <option key={item.key} value={item.key}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="workspace-action"
        onClick={controls.toggleDirection}
        aria-label={`Sort direction: ${controls.direction === "asc" ? "ascending" : "descending"}`}
        title="Toggle sort direction"
      >
        {controls.direction === "asc" ? "↑ Asc" : "↓ Desc"}
      </button>
      <small className="workspace-count">
        {controls.filtered.length} of {controls.total} {label}
      </small>
    </div>
  );
}
