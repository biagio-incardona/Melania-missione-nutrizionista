const initialLeads = require("./initial_leads.json");

const REDIS_KEY = "melania_crm_leads";

async function redisCommand(command, ...args) {
  const url = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;

  if (!url || !token) {
    console.warn("Upstash Redis credentials not detected in environment.");
    return null;
  }

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify([command, ...args])
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error(`Upstash API error (${res.status}):`, errText);
      return null;
    }

    const data = await res.json();
    return data.result;
  } catch (err) {
    console.error("Network error talking to Upstash Redis:", err);
    return null;
  }
}

async function getStoredLeads() {
  const raw = await redisCommand("GET", REDIS_KEY);
  if (raw) {
    try {
      const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    } catch (e) {
      console.error("Error parsing stored leads:", e);
    }
  }

  // Seed Redis with the curated 96 initial leads on first access
  console.log("Seeding Redis with initial leads...");
  await redisCommand("SET", REDIS_KEY, JSON.stringify(initialLeads));
  return initialLeads;
}

async function saveStoredLeads(leads) {
  await redisCommand("SET", REDIS_KEY, JSON.stringify(leads));
}

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  res.setHeader("Cache-Control", "no-store, no-cache, must-revalidate");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  try {
    // --- RESET ENDPOINT (?reset=true) ---
    if (req.query && req.query.reset === "true") {
      await redisCommand("SET", REDIS_KEY, JSON.stringify(initialLeads));
      return res.status(200).json({ success: true, message: "Database reset to 96 initial leads", leads: initialLeads });
    }

    // --- GET /api/leads ---
    if (req.method === "GET") {
      const leads = await getStoredLeads();
      return res.status(200).json({ leads, total: leads.length, storage: "upstash_redis" });
    }

    // --- POST /api/leads (Aggiungi nuovo contatto) ---
    if (req.method === "POST") {
      const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
      const leads = await getStoredLeads();

      const maxId = leads.reduce((max, l) => Math.max(max, Number(l.id) || 0), 0);
      const newLead = {
        ...body,
        id: maxId + 1,
        Stato_Candidatura: body.Stato_Candidatura || "Da contattare"
      };

      leads.push(newLead);
      await saveStoredLeads(leads);

      return res.status(201).json({ success: true, lead: newLead });
    }

    // --- PUT /api/leads?id=:id (Aggiorna contatto o note) ---
    if (req.method === "PUT") {
      const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
      const leadId = Number(req.query.id || body.id);

      if (!leadId) {
        return res.status(400).json({ error: "Missing lead ID" });
      }

      const leads = await getStoredLeads();
      const idx = leads.findIndex(l => Number(l.id) === leadId);

      if (idx === -1) {
        return res.status(404).json({ error: `Lead with ID ${leadId} not found` });
      }

      leads[idx] = { ...leads[idx], ...body, id: leadId };
      await saveStoredLeads(leads);

      return res.status(200).json({ success: true, lead: leads[idx] });
    }

    // --- DELETE /api/leads?id=:id ---
    if (req.method === "DELETE") {
      const body = typeof req.body === "string" ? JSON.parse(req.body) : (req.body || {});
      const leadId = Number(req.query.id || body.id);

      if (!leadId) {
        return res.status(400).json({ error: "Missing lead ID" });
      }

      let leads = await getStoredLeads();
      leads = leads.filter(l => Number(l.id) !== leadId);
      await saveStoredLeads(leads);

      return res.status(200).json({ success: true, id: leadId });
    }

    return res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    console.error("API error:", err);
    return res.status(500).json({ error: err.message || "Internal server error" });
  }
};
