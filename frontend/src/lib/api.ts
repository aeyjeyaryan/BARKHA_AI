// API Configuration and Types for Barkha.AI

const API_BASE_URL = "http://0.0.0.0:8000";

// Types matching the backend models
export interface SiteDetailsInput {
  site_name: string;
  latitude: number;
  longitude: number;
  roof_area: number;
  roof_material: string;
  roof_condition: string;
  soil_type: string;
  annual_rainfall: number;
  water_demand: number;
}

export interface AssessmentResult {
  assessment_id: string;
  harvestable_volume: number;
  recommended_option: string;
  storage_recommendation: {
    required_volume: number;
    recommended_volume: number;
    storage_days: number;
  };
  recharge_recommendation: {
    recharge_pit: {
      diameter: number;
      depth: number;
      area: number;
    };
    recharge_trench: {
      length: number;
      width: number;
      depth: number;
    };
    infiltration_rate: number;
    suitability_score: number;
  };
  cost_analysis: {
    storage_tank_cost: number;
    recharge_structure_cost: number;
    piping_cost: number;
    filtration_cost: number;
    labor_cost: number;
    material_contingency: number;
    tax: number;
    total_cost: number;
  };
  savings_analysis: {
    annual_water_saved: number;
    annual_cost_savings: number;
    monthly_savings: number;
    water_tariff_used: number;
  };
  safety_checks: string[];
  bill_of_quantities: {
    items: Array<{
      item: string;
      quantity: string;
      rate: number;
      amount: number;
    }>;
    total_cost: number;
  };
  payback_period: string | null; // Added to match backend
}

export interface Assessment {
  id: string;
  site_name: string;
  latitude: number;
  longitude: number;
  roof_area: number;
  roof_material: string;
  roof_condition: string;
  soil_type: string;
  annual_rainfall: number;
  water_demand: number;
  site_photos?: string[];
  assessment_data: any;
  recommendations: any;
  created_at: string;
  updated_at: string;
  is_synced: boolean;
}

// API Functions
class BarkhaAPI {
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const config: RequestInit = {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP error! status: ${response.status}, detail: ${errorText}`);
      }
      
      // For JSON responses
      if (response.headers.get('Content-Type')?.includes('application/json')) {
        return await response.json();
      }
      
      // For binary responses (e.g., PDF)
      return response as any;
    } catch (error) {
      console.error('API Request failed:', error);
      throw error;
    }
  }

  // Create new assessment
  async createAssessment(siteData: SiteDetailsInput): Promise<AssessmentResult> {
    return this.request<AssessmentResult>('/api/assess', {
      method: 'POST',
      body: JSON.stringify(siteData),
    });
  }

  // Get all assessments
  async getAssessments(skip = 0, limit = 100): Promise<Assessment[]> {
    return this.request<Assessment[]>(`/api/assessments?skip=${skip}&limit=${limit}`);
  }

  // Get specific assessment
  async getAssessment(assessmentId: string): Promise<Assessment> {
    return this.request<Assessment>(`/api/assessments/${assessmentId}`);
  }

  // Generate PDF report
  async generateReport(assessmentId: string): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-report/${assessmentId}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/pdf',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to generate report: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Generate report failed:', error);
      throw error;
    }
  }

  // Upload site photos
  async uploadPhotos(assessmentId: string, files: File[]): Promise<{ message: string }> {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });

    return this.request<{ message: string }>(`/api/upload-photos/${assessmentId}`, {
      method: 'POST',
      body: formData,
      headers: {}, // Remove Content-Type to let fetch set multipart/form-data boundary
    });
  }

  // Health check
  async healthCheck(): Promise<{ status: string; timestamp: string }> {
    return this.request<{ status: string; timestamp: string }>('/health');
  }

  // Satellite Analysis Methods
  async getSatelliteImage(latitude: number, longitude: number): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/satellite-image/download/${latitude}/${longitude}`, {
        method: 'GET',
        headers: {
          'Accept': 'image/png',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to fetch satellite image: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Get satellite image failed:', error);
      throw error;
    }
  }

  async analyzeRooftop(latitude: number, longitude: number, markedImage: File): Promise<any> {
    const formData = new FormData();
    formData.append('marked_image', markedImage);

    return this.request<any>(`/api/analyze-rooftop?latitude=${latitude}&longitude=${longitude}`, {
      method: 'POST',
      body: formData,
      headers: {}, // Remove Content-Type to let fetch set multipart/form-data boundary
    });
  }

  async quickDimensionsAnalysis(latitude: number, longitude: number, markedImage: File): Promise<any> {
    const formData = new FormData();
    formData.append('marked_image', markedImage);

    return this.request<any>(`/api/quick-dimensions?latitude=${latitude}&longitude=${longitude}`, {
      method: 'POST',
      body: formData,
      headers: {}, // Remove Content-Type to let fetch set multipart/form-data boundary
    });
  }

  async createAssessmentWithSatellite(siteData: SiteDetailsInput, markedImage?: File): Promise<AssessmentResult> {
    const formData = new FormData();
    formData.append('site_data', JSON.stringify(siteData));
    if (markedImage) {
      formData.append('marked_image', markedImage);
    }

    return this.request<AssessmentResult>('/api/assess-with-satellite', {
      method: 'POST',
      body: formData,
      headers: {}, // Remove Content-Type to let fetch set multipart/form-data boundary
    });
  }

  async downloadTemplateImage(latitude: number, longitude: number): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/template-image/download/${latitude}/${longitude}`, {
        method: 'GET',
        headers: {
          'Accept': 'image/png',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to download template: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Download template failed:', error);
      throw error;
    }
  }

  // Test PDF download functionality
  async testPdfDownload(): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/test-pdf-download`, {
        method: 'GET',
        headers: {
          'Accept': 'application/pdf',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to download test PDF: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Test PDF download failed:', error);
      throw error;
    }
  }

  async downloadPdfReport(assessmentId: string): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-report/${assessmentId}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/pdf',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to download PDF report: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('PDF report download failed:', error);
      throw error;
    }
  }

  async downloadTextReport(assessmentId: string): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/generate-text-report/${assessmentId}`, {
        method: 'GET',
        headers: {
          'Accept': 'text/plain',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to download text report: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Text report download failed:', error);
      throw error;
    }
  }

  async downloadBothReports(assessmentId: string): Promise<Blob> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/download-reports/${assessmentId}`, {
        method: 'GET',
        headers: {
          'Accept': 'application/zip',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to download reports: ${response.status} - ${errorText}`);
      }

      return await response.blob();
    } catch (error) {
      console.error('Reports download failed:', error);
      throw error;
    }
  }
}

export const api = new BarkhaAPI();

// Utility functions
export const formatCurrency = (amount: number): string => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

export const formatVolume = (volume: number): string => {
  return `${volume.toLocaleString('en-IN')} m³`;
};

export const formatDate = (dateString: string): string => {
  return new Date(dateString).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
};

// Constants
export const ROOF_MATERIALS = [
  'concrete',
  'tile', 
  'metal',
  'asbestos',
  'thatched'
] as const;

export const ROOF_CONDITIONS = [
  'good',
  'fair',
  'poor'
] as const;

export const SOIL_TYPES = [
  'sandy',
  'loamy', 
  'clay',
  'rocky'
] as const;

export const RECOMMENDATION_LABELS = {
  'storage_only': 'Storage System Only',
  'recharge_only': 'Recharge System Only', 
  'hybrid': 'Hybrid System (Storage + Recharge)',
  'storage_priority_hybrid': 'Storage Priority Hybrid',
  'not_feasible': 'Not Feasible'
} as const;