export interface SessionProvider {
  getAccessToken(): Promise<string | null>;
}

export const unavailableSessionProvider: SessionProvider = {
  async getAccessToken(): Promise<null> {
    return null;
  },
};
