// Minimal IndexedDB wrapper for the field harvest write-ahead log.
// One object store ("harvest_records") holding every crate captured on this
// device, each with a "synced" flag. This is the source of truth for the
// current load's running totals - the UI never needs the server to be
// reachable to keep working.
const IDB = (() => {
  const DB_NAME = "lw_field_db";
  const STORE = "harvest_records";
  let dbPromise = null;

  function open() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          const store = db.createObjectStore(STORE, { keyPath: "uuid" });
          store.createIndex("slip_number", "slip_number");
          store.createIndex("synced", "synced");
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbPromise;
  }

  async function tx(mode) {
    const db = await open();
    return db.transaction(STORE, mode).objectStore(STORE);
  }

  return {
    async add(record) {
      const store = await tx("readwrite");
      store.put(record);
    },
    async getBySlip(slipNumber) {
      const store = await tx("readonly");
      return new Promise((resolve) => {
        const idx = store.index("slip_number");
        const req = idx.getAll(slipNumber);
        req.onsuccess = () => resolve(req.result);
      });
    },
    async getUnsynced() {
      const store = await tx("readonly");
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result.filter((r) => !r.synced));
      });
    },
    async markSynced(uuids) {
      const store = await tx("readwrite");
      for (const uuid of uuids) {
        const getReq = store.get(uuid);
        getReq.onsuccess = () => {
          const rec = getReq.result;
          if (rec) {
            rec.synced = true;
            store.put(rec);
          }
        };
      }
    },
    async reassignSlip(uuids, newSlip) {
      const store = await tx("readwrite");
      for (const uuid of uuids) {
        const getReq = store.get(uuid);
        getReq.onsuccess = () => {
          const rec = getReq.result;
          if (rec) {
            rec.slip_number = newSlip;
            store.put(rec);
          }
        };
      }
    },
    async recent(limit = 5) {
      const store = await tx("readonly");
      return new Promise((resolve) => {
        const req = store.getAll();
        req.onsuccess = () => {
          const all = req.result.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
          resolve(all.slice(0, limit));
        };
      });
    },
  };
})();
