import { getConfig } from './config';

export type AuthUser = {
  id: string;
  email: string;
  role: 'user' | 'admin';
};

export function requireUser(): AuthUser {
  const { mockMode } = getConfig();
  if (mockMode) {
    const role = process.env.MOCK_USER_ROLE === 'admin' ? 'admin' : 'user';
    return {
      id: 'mock-user-1',
      email: role === 'admin' ? 'admin@gematr.local' : 'user@gematr.local',
      role,
    };
  }

  throw new Error('Clerk not wired');
}

export function requireAdmin(): AuthUser {
  const user = requireUser();
  if (user.role !== 'admin') {
    throw new Error('Admin role required');
  }

  return user;
}
