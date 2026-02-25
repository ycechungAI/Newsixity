"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { CityConfig, GeocodingResult } from "@/lib/weather/types";
import { searchCities } from "@/lib/weather/api";

interface CitySearchProps {
  onCitySelect: (city: CityConfig) => void;
}

export default function CitySearch({ onCitySelect }: CitySearchProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeocodingResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [noResults, setNoResults] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearch = useCallback(async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setResults([]);
      setIsOpen(false);
      setNoResults(false);
      return;
    }
    setIsSearching(true);
    setNoResults(false);
    try {
      const data = await searchCities(searchQuery);
      const cityResults = data.results ?? [];
      setResults(cityResults);
      setIsOpen(true);
      setNoResults(cityResults.length === 0);
    } catch {
      setResults([]);
      setNoResults(true);
    } finally {
      setIsSearching(false);
    }
  }, []);

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const value = e.target.value;
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => handleSearch(value), 300);
  }

  function handleSelectCity(result: GeocodingResult) {
    const city: CityConfig = {
      name: result.name,
      country: result.country,
      latitude: result.latitude,
      longitude: result.longitude,
    };
    onCitySelect(city);
    setQuery("");
    setResults([]);
    setIsOpen(false);
    setNoResults(false);
  }

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <input
        type="text"
        value={query}
        onChange={handleInputChange}
        placeholder={isSearching ? "Searching…" : "Add city…"}
        className="wx-search-input"
      />
      {isOpen && (
        <div className="wx-dropdown">
          {noResults ? (
            <div className="wx-dropdown-item" style={{ color: "var(--muted)" }}>No cities found</div>
          ) : (
            results.map((result) => (
              <button
                key={result.id}
                className="wx-dropdown-item"
                onClick={() => handleSelectCity(result)}
              >
                <span className="wx-dropdown-city">{result.name}</span>
                <span className="wx-dropdown-region">
                  {result.admin1 ? `${result.admin1}, ` : ""}{result.country}
                </span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
