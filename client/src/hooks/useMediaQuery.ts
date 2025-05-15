"use client";

import { useState, useEffect } from "react";

/**
 * Custom hook to check if the current viewport matches a media query
 * @param query The media query to check against (e.g. '(min-width: 768px)')
 * @returns Boolean indicating if the viewport matches the media query
 */
export function useMediaQuery(query: string): boolean {
  // Initialize with null for SSR (will be updated on client)
  const [matches, setMatches] = useState<boolean>(false);
  
  useEffect(() => {
    // Only run on client side
    if (typeof window === "undefined") return;
    
    // Create the media query
    const media = window.matchMedia(query);
    
    // Handle changes and set initial state
    const updateMatches = () => {
      setMatches(media.matches);
    };
    
    // Set initial value
    updateMatches();
    
    // Set up listener for changes
    media.addEventListener("change", updateMatches);
    
    // Clean up
    return () => {
      media.removeEventListener("change", updateMatches);
    };
  }, [query]);
  
  return matches;
}

/**
 * Predefined screen size breakpoints matching Tailwind's defaults
 */
export const breakpoints = {
  sm: "(min-width: 640px)",
  md: "(min-width: 768px)",
  lg: "(min-width: 1024px)",
  xl: "(min-width: 1280px)",
  "2xl": "(min-width: 1536px)",
};

/**
 * Custom hooks for each breakpoint
 */
export function useIsMobile(): boolean {
  return !useMediaQuery(breakpoints.md);
}

export function useIsTablet(): boolean {
  const isAtLeastMd = useMediaQuery(breakpoints.md);
  const isLessThanLg = !useMediaQuery(breakpoints.lg);
  return isAtLeastMd && isLessThanLg;
}

export function useIsDesktop(): boolean {
  return useMediaQuery(breakpoints.lg);
}

export function useIsSmallScreen(): boolean {
  return !useMediaQuery(breakpoints.sm);
}

export function useIsMediumScreen(): boolean {
  return useMediaQuery(breakpoints.md);
}

export function useIsLargeScreen(): boolean {
  return useMediaQuery(breakpoints.lg);
}

export function useIsExtraLargeScreen(): boolean {
  return useMediaQuery(breakpoints.xl);
} 