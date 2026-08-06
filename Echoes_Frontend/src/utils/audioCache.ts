import { openDB, type DBSchema } from "idb";

const DB_NAME = "echoes-audio-cache";
const STORE_NAME = "audio-blobs";
const DB_VERSION = 1;

interface AudioCacheDB extends DBSchema {
  [STORE_NAME]: {
    key: string;
    value: Blob;
  };
}

const dbPromise = openDB<AudioCacheDB>(DB_NAME, DB_VERSION, {
  upgrade(db) {
    if (!db.objectStoreNames.contains(STORE_NAME)) {
      db.createObjectStore(STORE_NAME);
    }
  }
});

class AudioCache {
  async get(key: string): Promise<Blob | undefined> {
    return (await dbPromise).get(STORE_NAME, key);
  }

  async set(key: string, blob: Blob): Promise<string> {
    return (await dbPromise).put(STORE_NAME, blob, key);
  }

  async clear(): Promise<void> {
    return (await dbPromise).clear(STORE_NAME);
  }
}

export const audioCache = new AudioCache();
