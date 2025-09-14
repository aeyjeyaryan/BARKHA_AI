
// src/lib/utils.ts
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// src/lib/api.ts - API utilities for satellite analysis
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api';

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

export class SatelliteAPI {
  static async getSatelliteImage(latitude: number, longitude: number): Promise<Blob> {
    const response = await fetch(
      `${API_BASE}/satellite-image/download/${latitude}/${longitude}`,
      { method: 'GET' }
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch satellite image: ${response.statusText}`);
    }
    
    return response.blob();
  }

  static async analyzeRooftop(
    latitude: number, 
    longitude: number, 
    markedImageFile: File
  ): Promise<any> {
    const formData = new FormData();
    formData.append('marked_image', markedImageFile);

    const response = await fetch(
      `${API_BASE}/analyze-rooftop?latitude=${latitude}&longitude=${longitude}`,
      {
        method: 'POST',
        body: formData,
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Analysis failed');
    }

    return data;
  }

  static async quickAnalysis(
    latitude: number, 
    longitude: number, 
    markedImageFile: File
  ): Promise<any> {
    const formData = new FormData();
    formData.append('marked_image', markedImageFile);

    const response = await fetch(
      `${API_BASE}/quick-dimensions?latitude=${latitude}&longitude=${longitude}`,
      {
        method: 'POST',
        body: formData,
      }
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || 'Quick analysis failed');
    }

    return data;
  }

  static async getHealthStatus(): Promise<any> {
    const response = await fetch(`${API_BASE}/dimensions/health`);
    return response.json();
  }
}

// Utility functions for coordinate validation
export const validateCoordinates = (lat: number, lon: number): boolean => {
  return lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
};

// Format numbers for display
export const formatNumber = (num: number, decimals = 0): string => {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: decimals,
    minimumFractionDigits: decimals,
  }).format(num);
};

// Format file size
export const formatFileSize = (bytes: number): string => {
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  if (bytes === 0) return '0 Bytes';
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
};

// Month names for display
export const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

// Image validation utilities
export const validateImageFile = (file: File): { valid: boolean; error?: string } => {
  const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp'];
  const maxSize = 10 * 1024 * 1024; // 10MB

  if (!allowedTypes.includes(file.type)) {
    return {
      valid: false,
      error: 'Please select a valid image file (JPEG, PNG, or BMP)'
    };
  }

  if (file.size > maxSize) {
    return {
      valid: false,
      error: 'File size must be less than 10MB'
    };
  }

  return { valid: true };
};