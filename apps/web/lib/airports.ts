/**
 * Monitored airport codes, used to prerender /airports/[code] (metadata in <head>).
 * Mirrors services/api/app/data/airports.csv — a unit test keeps them in sync.
 */
export const MONITORED_AIRPORTS = ["ATL", "AUS", "BNA", "BOS", "BWI", "CLE", "CLT", "CMH", "CVG", "DAL", "DCA", "DEN", "DFW", "DTW", "EWR", "FLL", "HNL", "HOU", "IAD", "IAH", "IND", "JAX", "JFK", "LAS", "LAX", "LGA", "MCI", "MCO", "MDW", "MIA", "MSP", "MSY", "OAK", "ORD", "PDX", "PHL", "PHX", "PIT", "RDU", "RSW", "SAN", "SAT", "SEA", "SFO", "SJC", "SLC", "SMF", "SNA", "STL", "TPA"] as const;
