---
title: API Client Setup Template
description: Production-ready TypeScript API client with Axios, interceptors, error handling, and retry logic
tags: [template, api-client, typescript, axios, frontend]
type: template
version: "1.0.0"
category: frontend
---

# API Client Setup Template

## Overview

This template provides a production-ready TypeScript API client built on Axios with request/response interceptors, automatic token refresh, retry logic, request cancellation, type-safe endpoints, and comprehensive error handling.

**Features:**
- Type-safe API requests and responses
- Automatic JWT token management
- Request/response interceptors
- Retry logic with exponential backoff
- Request cancellation
- Error handling and transformation
- Mock data support for development
- Request queuing during token refresh

## Project Structure

```
src/
├── api/
│   ├── client.ts              # Base API client
│   ├── config.ts              # Configuration
│   ├── interceptors.ts        # Request/response interceptors
│   ├── errors.ts              # Error handling
│   ├── types.ts               # Type definitions
│   ├── endpoints/
│   │   ├── auth.ts            # Auth endpoints
│   │   ├── users.ts           # User endpoints
│   │   └── posts.ts           # Post endpoints
│   ├── mocks/
│   │   ├── handlers.ts        # MSW handlers
│   │   └── data.ts            # Mock data
│   └── utils/
│       ├── retry.ts           # Retry logic
│       └── queue.ts           # Request queue
└── types/
    ├── auth.ts
    ├── user.ts
    └── api.ts
```

## Core Files

### 1. api/config.ts - Configuration

```typescript
export const API_CONFIG = {
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  timeout: 10000,
  withCredentials: false,
  headers: {
    'Content-Type': 'application/json',
  },
  retry: {
    maxRetries: 3,
    retryDelay: 1000,
    retryableStatuses: [408, 429, 500, 502, 503, 504],
  },
};

export const TOKEN_STORAGE = {
  accessToken: 'access_token',
  refreshToken: 'refresh_token',
};
```

### 2. api/types.ts - Type Definitions

```typescript
export interface ApiResponse<T> {
  data: T;
  message?: string;
  meta?: {
    total?: number;
    page?: number;
    limit?: number;
  };
}

export interface ApiError {
  error: string;
  message: string;
  details?: Array<{
    field?: string;
    message: string;
    code?: string;
  }>;
  timestamp: string;
  path: string;
  request_id: string;
}

export interface PaginatedParams {
  page?: number;
  limit?: number;
  sort?: string;
  order?: 'asc' | 'desc';
}

export interface RequestConfig {
  skipAuth?: boolean;
  skipRetry?: boolean;
  signal?: AbortSignal;
}
```

### 3. api/errors.ts - Error Handling

```typescript
import { AxiosError } from 'axios';
import { ApiError } from './types';

export class ApiClientError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public errorCode: string,
    public details?: any[],
    public requestId?: string
  ) {
    super(message);
    this.name = 'ApiClientError';
  }

  static fromAxiosError(error: AxiosError<ApiError>): ApiClientError {
    if (error.response) {
      const { data, status } = error.response;
      return new ApiClientError(
        data.message || 'An error occurred',
        status,
        data.error,
        data.details,
        data.request_id
      );
    }

    if (error.request) {
      return new ApiClientError(
        'No response from server',
        0,
        'NETWORK_ERROR'
      );
    }

    return new ApiClientError(
      error.message,
      0,
      'REQUEST_ERROR'
    );
  }

  isAuthError(): boolean {
    return this.statusCode === 401 || this.errorCode === 'AUTHENTICATION_ERROR';
  }

  isValidationError(): boolean {
    return this.statusCode === 400 || this.errorCode === 'VALIDATION_ERROR';
  }

  isServerError(): boolean {
    return this.statusCode >= 500;
  }
}
```

### 4. api/client.ts - API Client

```typescript
import axios, { AxiosInstance, AxiosRequestConfig, AxiosError } from 'axios';
import { API_CONFIG, TOKEN_STORAGE } from './config';
import { ApiClientError } from './errors';
import { ApiResponse, RequestConfig } from './types';
import { retryRequest } from './utils/retry';
import { RequestQueue } from './utils/queue';

class ApiClient {
  private client: AxiosInstance;
  private requestQueue: RequestQueue;
  private isRefreshing = false;

  constructor() {
    this.client = axios.create({
      baseURL: API_CONFIG.baseURL,
      timeout: API_CONFIG.timeout,
      withCredentials: API_CONFIG.withCredentials,
      headers: API_CONFIG.headers,
    });

    this.requestQueue = new RequestQueue();
    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor
    this.client.interceptors.request.use(
      (config) => {
        // Add auth token
        const token = localStorage.getItem(TOKEN_STORAGE.accessToken);
        if (token && !config.headers.skipAuth) {
          config.headers.Authorization = `Bearer ${token}`;
        }

        // Add request ID for tracking
        config.headers['X-Request-ID'] = crypto.randomUUID();

        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as AxiosRequestConfig & {
          _retry?: boolean;
          _retryCount?: number;
        };

        // Handle 401 - Token expired
        if (error.response?.status === 401 && !originalRequest._retry) {
          if (this.isRefreshing) {
            // Queue request while refreshing
            return this.requestQueue.add(() => this.client.request(originalRequest));
          }

          originalRequest._retry = true;
          this.isRefreshing = true;

          try {
            // Refresh token
            const refreshToken = localStorage.getItem(TOKEN_STORAGE.refreshToken);
            if (!refreshToken) {
              throw new Error('No refresh token available');
            }

            const response = await axios.post(
              `${API_CONFIG.baseURL}/api/v1/auth/refresh`,
              { refresh_token: refreshToken }
            );

            const { access_token, refresh_token } = response.data;
            localStorage.setItem(TOKEN_STORAGE.accessToken, access_token);
            localStorage.setItem(TOKEN_STORAGE.refreshToken, refresh_token);

            // Retry original request
            this.isRefreshing = false;
            this.requestQueue.process();

            return this.client.request(originalRequest);
          } catch (refreshError) {
            // Refresh failed - logout
            this.isRefreshing = false;
            this.requestQueue.clear();
            localStorage.clear();
            window.location.href = '/login';
            return Promise.reject(refreshError);
          }
        }

        // Retry logic
        if (
          error.response &&
          API_CONFIG.retry.retryableStatuses.includes(error.response.status) &&
          !originalRequest.skipRetry
        ) {
          return retryRequest(
            () => this.client.request(originalRequest),
            originalRequest._retryCount || 0
          );
        }

        return Promise.reject(ApiClientError.fromAxiosError(error));
      }
    );
  }

  async get<T>(url: string, config?: RequestConfig): Promise<T> {
    const response = await this.client.get<ApiResponse<T>>(url, config);
    return response.data.data;
  }

  async post<T>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    const response = await this.client.post<ApiResponse<T>>(url, data, config);
    return response.data.data;
  }

  async put<T>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    const response = await this.client.put<ApiResponse<T>>(url, data, config);
    return response.data.data;
  }

  async patch<T>(url: string, data?: any, config?: RequestConfig): Promise<T> {
    const response = await this.client.patch<ApiResponse<T>>(url, data, config);
    return response.data.data;
  }

  async delete<T>(url: string, config?: RequestConfig): Promise<T> {
    const response = await this.client.delete<ApiResponse<T>>(url, config);
    return response.data.data;
  }

  // Create AbortController for request cancellation
  createCancelToken(): AbortController {
    return new AbortController();
  }
}

export const apiClient = new ApiClient();
```

### 5. api/utils/retry.ts - Retry Logic

```typescript
import { API_CONFIG } from '../config';

export async function retryRequest<T>(
  requestFn: () => Promise<T>,
  retryCount: number = 0
): Promise<T> {
  try {
    return await requestFn();
  } catch (error) {
    if (retryCount >= API_CONFIG.retry.maxRetries) {
      throw error;
    }

    // Exponential backoff with jitter
    const delay = Math.min(
      API_CONFIG.retry.retryDelay * Math.pow(2, retryCount) * (0.5 + Math.random() * 0.5),
      30000 // Max 30 seconds
    );

    await new Promise((resolve) => setTimeout(resolve, delay));

    return retryRequest(requestFn, retryCount + 1);
  }
}
```

### 6. api/utils/queue.ts - Request Queue

```typescript
type QueuedRequest = () => Promise<any>;

export class RequestQueue {
  private queue: QueuedRequest[] = [];
  private processing = false;

  add(request: QueuedRequest): Promise<any> {
    return new Promise((resolve, reject) => {
      this.queue.push(async () => {
        try {
          const result = await request();
          resolve(result);
        } catch (error) {
          reject(error);
        }
      });
    });
  }

  async process() {
    if (this.processing || this.queue.length === 0) {
      return;
    }

    this.processing = true;

    while (this.queue.length > 0) {
      const request = this.queue.shift();
      if (request) {
        await request();
      }
    }

    this.processing = false;
  }

  clear() {
    this.queue = [];
  }
}
```

### 7. api/endpoints/users.ts - User Endpoints

```typescript
import { apiClient } from '../client';
import { PaginatedParams } from '../types';

export interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface CreateUserData {
  email: string;
  full_name: string;
  password: string;
}

export interface UpdateUserData {
  email?: string;
  full_name?: string;
  password?: string;
}

export const usersApi = {
  // List users with pagination
  list: (params?: PaginatedParams) => {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.set('page', params.page.toString());
    if (params?.limit) queryParams.set('limit', params.limit.toString());

    return apiClient.get<User[]>(`/api/v1/users?${queryParams}`);
  },

  // Get user by ID
  getById: (userId: number) => {
    return apiClient.get<User>(`/api/v1/users/${userId}`);
  },

  // Create user
  create: (data: CreateUserData) => {
    return apiClient.post<User>('/api/v1/users', data);
  },

  // Update user
  update: (userId: number, data: UpdateUserData) => {
    return apiClient.patch<User>(`/api/v1/users/${userId}`, data);
  },

  // Delete user
  delete: (userId: number) => {
    return apiClient.delete<void>(`/api/v1/users/${userId}`);
  },

  // Search users
  search: (query: string, signal?: AbortSignal) => {
    return apiClient.get<User[]>(`/api/v1/users/search?q=${query}`, { signal });
  },
};
```

### 8. React Hook Integration

```typescript
import { useState, useEffect } from 'react';
import { usersApi, User } from '@/api/endpoints/users';
import { ApiClientError } from '@/api/errors';

export function useUsers() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ApiClientError | null>(null);

  const fetchUsers = async (page: number = 1, limit: number = 20) => {
    try {
      setLoading(true);
      setError(null);
      const data = await usersApi.list({ page, limit });
      setUsers(data);
    } catch (err) {
      setError(err as ApiClientError);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  return { users, loading, error, refetch: fetchUsers };
}

// With request cancellation
export function useUserSearch(query: string) {
  const [results, setResults] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }

    const controller = apiClient.createCancelToken();

    const search = async () => {
      try {
        setLoading(true);
        const data = await usersApi.search(query, controller.signal);
        setResults(data);
      } catch (err) {
        if (err.name !== 'CanceledError') {
          console.error(err);
        }
      } finally {
        setLoading(false);
      }
    };

    search();

    return () => {
      controller.abort();
    };
  }, [query]);

  return { results, loading };
}
```

### 9. Mock Data for Development

**api/mocks/handlers.ts:**
```typescript
import { rest } from 'msw';
import { API_CONFIG } from '../config';

export const handlers = [
  // Mock user list
  rest.get(`${API_CONFIG.baseURL}/api/v1/users`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: [
          { id: 1, email: 'user1@example.com', full_name: 'User One', is_active: true },
          { id: 2, email: 'user2@example.com', full_name: 'User Two', is_active: true },
        ],
        meta: { total: 2, page: 1, limit: 20 },
      })
    );
  }),

  // Mock login
  rest.post(`${API_CONFIG.baseURL}/api/v1/auth/login`, (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          access_token: 'mock-access-token',
          refresh_token: 'mock-refresh-token',
        },
      })
    );
  }),
];
```

## Testing

```typescript
import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { handlers } from './mocks/handlers';
import { usersApi } from './endpoints/users';

const server = setupServer(...handlers);

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('usersApi', () => {
  it('should fetch users', async () => {
    const users = await usersApi.list();
    expect(users).toHaveLength(2);
    expect(users[0].email).toBe('user1@example.com');
  });
});
```

## Related Templates & Skills

- [React TypeScript App](./react-typescript-app.md) - Frontend integration
- [FastAPI Starter](./fastapi-starter.md) - Backend API
- [API Development](../skills/api-development.md) - API design

---

**Version:** 1.0.0
**Last Updated:** 2025-10-25
**Maintainer:** Conventions MCP
**License:** MIT
