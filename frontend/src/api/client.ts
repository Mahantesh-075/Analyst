/**
 * API client for Analyst backend services.
 * Automatically injects JWT Bearer tokens and handles error responses.
 */

const BASE_URL = '/api/v1';

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, any>;
  request_id?: string;
}

class ApiClient {
  private getToken(): string | null {
    return localStorage.getItem('analyst_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {}),
    };

    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    const res = await fetch(`${BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (res.status === 401) {
      localStorage.removeItem('analyst_token');
      localStorage.removeItem('analyst_user');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }

    if (!res.ok) {
      let errData: any = {};
      try {
        errData = await res.json();
      } catch {
        errData = { message: res.statusText || 'Request failed' };
      }

      let message = errData.error?.message || errData.message;
      if (!message && Array.isArray(errData.detail)) {
        message = errData.detail.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
      } else if (!message && errData.error?.details?.errors) {
        const errs = errData.error.details.errors;
        if (Array.isArray(errs)) {
          message = errs.map((e: any) => e.msg || JSON.stringify(e)).join(', ');
        }
      } else if (!message && typeof errData.detail === 'string') {
        message = errData.detail;
      }

      const error: ApiError = {
        code: errData.error?.code || errData.code || 'UNKNOWN_ERROR',
        message: message || 'An unexpected error occurred',
        details: errData.error?.details || errData.details,
        request_id: errData.request_id,
      };
      throw error;
    }

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      return (await res.json()) as T;
    }
    return (await res.text()) as unknown as T;
  }

  // Auth Endpoints
  async register(data: { email: string; password: string; display_name?: string }) {
    return this.request<{ access_token: string; refresh_token: string; user: any }>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async login(data: { email: string; password: string }) {
    return this.request<{ access_token: string; refresh_token: string; user: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  // Dataset Endpoints
  async getDatasets() {
    const res = await this.request<any>('/datasets');
    return res.items || (Array.isArray(res) ? res : []);
  }

  async getDataset(id: string) {
    return this.request<any>(`/datasets/${id}`);
  }

  async getUploadUrl(filename: string, fileSizeBytes: number) {
    return this.request<{ upload_url: string; s3_key: string }>('/datasets/upload-url', {
      method: 'POST',
      body: JSON.stringify({ filename, file_size_bytes: fileSizeBytes }),
    });
  }

  async createDataset(data: { name: string; source_filename: string; s3_key: string; description?: string }) {
    return this.request<any>('/datasets', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async triggerIngest(datasetId: string) {
    return this.request<any>(`/jobs/datasets/${datasetId}/ingest`, {
      method: 'POST',
    });
  }

  // Profile Endpoints
  async getProfile(datasetId: string) {
    return this.request<any>(`/datasets/${datasetId}/profile`);
  }

  async getSample(datasetId: string) {
    return this.request<{ columns: string[]; sample: any[] }>(`/datasets/${datasetId}/sample`);
  }

  // Proposal & Apply Endpoints
  async generateProposals(datasetId: string) {
    return this.request<any[]>(`/datasets/${datasetId}/proposals/generate`, {
      method: 'POST',
    });
  }

  async getProposals(datasetId: string) {
    return this.request<any[]>(`/datasets/${datasetId}/proposals`);
  }

  async updateProposal(datasetId: string, proposalId: string, status: 'accepted' | 'rejected' | 'pending') {
    return this.request<any>(`/datasets/${datasetId}/proposals/${proposalId}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
  }

  async bulkUpdateProposals(datasetId: string, proposalIds: string[], status: 'accepted' | 'rejected') {
    return this.request<{ updated: number }>(`/datasets/${datasetId}/proposals/bulk`, {
      method: 'POST',
      body: JSON.stringify({ proposal_ids: proposalIds, status }),
    });
  }

  async applyCleaning(datasetId: string) {
    return this.request<any>(`/datasets/${datasetId}/apply`, {
      method: 'POST',
    });
  }

  // Dashboard & Safe Query
  async getDashboard(datasetId: string) {
    return this.request<any>(`/datasets/${datasetId}/dashboard`);
  }

  async executeSafeQuery(datasetId: string, queryPayload: any) {
    return this.request<any>(`/datasets/${datasetId}/query`, {
      method: 'POST',
      body: JSON.stringify(queryPayload),
    });
  }

  // Exports
  async getExportText(datasetId: string, format: 'python' | 'sql' | 'csv') {
    const token = this.getToken();
    const res = await fetch(`${BASE_URL}/datasets/${datasetId}/export/${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Export failed with status ${res.status}`);
    return res.text();
  }

  async downloadExport(datasetId: string, format: 'csv' | 'parquet' | 'python' | 'sql', filename: string) {
    const token = this.getToken();
    const res = await fetch(`${BASE_URL}/datasets/${datasetId}/export/${format}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Download failed with status ${res.status}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  }
}

export const api = new ApiClient();
