import java.util.*;

public class Question1a {

    static class Point {
        int x, y;
        Point(int x, int y) {
            this.x = x;
            this.y = y;
        }
    }

    public static int maxCollinearPoints(Point[] points) {
        int n = points.length;
        if (n < 2) return n;

        int maxCount = 0;

        for (int i = 0; i < n; i++) {
            Map<String, Integer> slopes = new HashMap<>();
            for (int j = 0; j < n; j++) {
                if (i == j) continue;

                int dx = points[j].x - points[i].x;
                int dy = points[j].y - points[i].y;

                String slope;
                if (dx == 0) {
                    slope = "INF"; // vertical line
                } else {
                    int gcd = gcd(dy, dx);
                    dy /= gcd;
                    dx /= gcd;
                    slope = dy + "/" + dx; // store slope as string to avoid float precision issues
                }

                slopes.put(slope, slopes.getOrDefault(slope, 0) + 1);
            }

            int currentMax = slopes.values().stream().max(Integer::compareTo).orElse(0) + 1; // +1 to include reference point
            maxCount = Math.max(maxCount, currentMax);
        }

        return maxCount;
    }

    // Helper function to calculate GCD
    private static int gcd(int a, int b) {
        if (b == 0) return a;
        return gcd(b, a % b);
    }

    public static void main(String[] args) {
        Point[] customerLocations = {
            new Point(1, 1),
            new Point(2, 2),
            new Point(3, 3),
            new Point(4, 2)
        };

        System.out.println("Maximum collinear points: " + maxCollinearPoints(customerLocations));
    }
}
