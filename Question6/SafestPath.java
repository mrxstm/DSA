import java.util.*;

public class SafestPath {

    // Graph: adjacency list with safety probabilities
    // Map<source, List<[destination, probability]>>
    static Map<String, List<double[]>> buildGraph() {
        Map<String, List<double[]>> graph = new HashMap<>();

        graph.put("KTM", Arrays.asList(
            new double[]{0, 0.90},  // JA
            new double[]{1, 0.80}   // JB
        ));
        graph.put("JA", Arrays.asList(
            new double[]{2, 0.90},  // KTM
            new double[]{3, 0.95},  // PH
            new double[]{4, 0.70}   // BS
        ));
        graph.put("JB", Arrays.asList(
            new double[]{2, 0.80},  // KTM
            new double[]{0, 0.60},  // JA
            new double[]{4, 0.90}   // BS
        ));
        graph.put("PH", Arrays.asList(
            new double[]{0, 0.95},  // JA
            new double[]{4, 0.85}   // BS
        ));
        graph.put("BS", Arrays.asList(
            new double[]{0, 0.70},  // JA
            new double[]{1, 0.90},  // JB
            new double[]{3, 0.85}   // PH
        ));

        return graph;
    }

    public static void main(String[] args) {

        // Node list (index-based for clarity)
        String[] nodes = {"JA", "JB", "KTM", "PH", "BS"};

        // Graph as adjacency list using node names
        Map<String, List<Object[]>> graph = new HashMap<>();
        graph.put("KTM", Arrays.asList(new Object[]{"JA", 0.90},
                                       new Object[]{"JB", 0.80}));
        graph.put("JA",  Arrays.asList(new Object[]{"KTM", 0.90},
                                       new Object[]{"PH",  0.95},
                                       new Object[]{"BS",  0.70}));
        graph.put("JB",  Arrays.asList(new Object[]{"KTM", 0.80},
                                       new Object[]{"JA",  0.60},
                                       new Object[]{"BS",  0.90}));
        graph.put("PH",  Arrays.asList(new Object[]{"JA",  0.95},
                                       new Object[]{"BS",  0.85}));
        graph.put("BS",  Arrays.asList(new Object[]{"JA",  0.70},
                                       new Object[]{"JB",  0.90},
                                       new Object[]{"PH",  0.85}));

        String source = "KTM";

        // ── Dijkstra with -log(p) transformation ─────────────────────────
        // dist[node] = minimum sum of -log(p(e)) from source
        Map<String, Double> dist = new HashMap<>();
        Map<String, String> prev = new HashMap<>();

        for (String node : graph.keySet()) {
            dist.put(node, Double.MAX_VALUE);
            prev.put(node, null);
        }
        dist.put(source, 0.0);

        // Min-heap: [transformedDistance, nodeName]
        // PriorityQueue sorted by transformed distance (ascending)
        PriorityQueue<double[]> heap = new PriorityQueue<>(
            Comparator.comparingDouble(a -> a[0])
        );
        // Store index mapping for heap (use parallel name array)
        Map<Double, String> indexMap = new HashMap<>();

        // We use a Object[] heap to carry both distance and node name
        PriorityQueue<Object[]> pq = new PriorityQueue<>(
            Comparator.comparingDouble(a -> (double) a[0])
        );
        pq.offer(new Object[]{0.0, source});

        while (!pq.isEmpty()) {
            Object[] top  = pq.poll();
            double   curDist = (double) top[0];
            String   u       = (String) top[1];

            // Skip stale entries
            if (curDist > dist.get(u)) continue;

            // RELAX each outgoing edge
            for (Object[] edge : graph.get(u)) {
                String  v    = (String) edge[0];
                double  prob = (double) edge[1];

                // Transformed weight: w(e) = -log(p(e))
                double w = -Math.log(prob);

                // Modified RELAX condition: minimise sum of -log(p)
                // Equivalent to maximising product of p(e)
                if (dist.get(u) + w < dist.get(v)) {
                    dist.put(v, dist.get(u) + w);
                    prev.put(v, u);
                    pq.offer(new Object[]{dist.get(v), v});
                }
            }
        }

        // ── Print results ─────────────────────────────────────────────────
        System.out.println("Safest paths from " + source + ":");
        System.out.println("-".repeat(50));

        String[] targets = {"JA", "JB", "PH", "BS"};
        for (String target : targets) {
            // Reconstruct path
            List<String> path = new ArrayList<>();
            String node = target;
            while (node != null) {
                path.add(0, node);
                node = prev.get(node);
            }

            // Calculate actual safety probability
            double safety = 1.0;
            for (int i = 0; i < path.size() - 1; i++) {
                String from = path.get(i);
                String to   = path.get(i + 1);
                for (Object[] edge : graph.get(from)) {
                    if (edge[0].equals(to)) {
                        safety *= (double) edge[1];
                        break;
                    }
                }
            }

            System.out.printf("KTM -> %s%n", target);
            System.out.printf("  Path   : %s%n",
                              String.join(" -> ", path));
            System.out.printf("  Safety : %.4f%n", safety);
            System.out.printf("  -log sum: %.4f%n%n", dist.get(target));
        }
    }
}
