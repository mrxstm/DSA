import java.util.*;

class EnergySource {
    String name;
    String type; // Solar, Hydro, Diesel
    int maxCapacity; // kWh per hour
    int startHour;
    int endHour;
    double cost; // Rs/kWh

    public EnergySource(String name, String type, int maxCapacity, int startHour, int endHour, double cost) {
        this.name = name;
        this.type = type;
        this.maxCapacity = maxCapacity;
        this.startHour = startHour;
        this.endHour = endHour;
        this.cost = cost;
    }
}

class Allocation {
    int solar, hydro, diesel;

    public int total() {
        return solar + hydro + diesel;
    }
}

public class Question4 {

    public static void main(String[] args) {

        // ----------------- Input Data -----------------
        // Hourly demand table: Hour, District A, B, C
        int[][] demand = {
            {6, 20, 15, 25},
            {7, 22, 16, 28},
            {8, 25, 18, 30},
            {9, 30, 20, 35},
            {17, 35, 25, 40}, // Peak hour with Diesel available
            {18, 32, 22, 38}
        };

        EnergySource[] sources = {
            new EnergySource("Solar", "Solar", 50, 6, 18, 1.0),
            new EnergySource("Hydro", "Hydro", 40, 0, 24, 1.5),
            new EnergySource("Diesel", "Diesel", 60, 17, 23, 3.0)
        };

        double totalCost = 0;
        int totalEnergy = 0;
        int renewableEnergy = 0;
        Set<Integer> dieselUsedHours = new HashSet<>();

        // ----------------- Allocation per Hour -----------------
        System.out.printf("%-5s %-10s %-6s %-6s %-6s %-6s %-6s %-6s\n",
                "Hour", "District", "Solar", "Hydro", "Diesel", "Total", "Demand", "%Fulfilled");

        for (int[] h : demand) {
            int hour = h[0];
            int[] districtDemand = Arrays.copyOfRange(h, 1, h.length);

            Allocation[] allocations = allocateEnergy(districtDemand, sources, hour);

            // Print allocations
            for (int i = 0; i < districtDemand.length; i++) {
                int solar = allocations[i].solar;
                int hydro = allocations[i].hydro;
                int diesel = allocations[i].diesel;
                int totalSupplied = allocations[i].total();
                int actualDemand = districtDemand[i];
                double percent = (totalSupplied * 100.0) / actualDemand;

                System.out.printf("%-5d %-10s %-6d %-6d %-6d %-6d %-6d %-6.1f\n",
                        hour, "D" + (char)('A'+i), solar, hydro, diesel, totalSupplied, actualDemand, percent);

                // Update analysis
                totalCost += solar * 1.0 + hydro * 1.5 + diesel * 3.0;
                totalEnergy += totalSupplied;
                renewableEnergy += solar + hydro;
                if (diesel > 0) dieselUsedHours.add(hour);
            }
        }

        // ----------------- Analysis -----------------
        System.out.println("\n--- Analysis ---");
        System.out.println("Total cost: Rs. " + totalCost);
        System.out.printf("Renewable energy %%: %.2f%%\n", (renewableEnergy * 100.0) / totalEnergy);
        System.out.print("Diesel used in hours: ");
        if (dieselUsedHours.isEmpty()) System.out.println("None");
        else dieselUsedHours.forEach(h -> System.out.print(h + " "));
        System.out.println();
    }

    // ----------------- Core Allocation Function -----------------
    public static Allocation[] allocateEnergy(int[] districtDemand, EnergySource[] sources, int hour) {
        Allocation[] allocations = new Allocation[districtDemand.length];
        for (int i = 0; i < districtDemand.length; i++) allocations[i] = new Allocation();

        // Filter available sources
        List<EnergySource> available = new ArrayList<>();
        for (EnergySource s : sources) {
            if (hour >= s.startHour && hour <= s.endHour) available.add(s);
        }

        // Sort by cost ascending (Greedy)
        available.sort(Comparator.comparingDouble(s -> s.cost));

        // Allocation proceeds in sorted order
        for (EnergySource src : available) {
            int remainingCapacity = src.maxCapacity;

            for (int i = 0; i < districtDemand.length; i++) {
                int demand = districtDemand[i];
                int alreadyAllocated = (src.name.equals("Solar") ? allocations[i].solar :
                                       src.name.equals("Hydro") ? allocations[i].hydro :
                                       allocations[i].diesel);

                // kWh to allocate with ±10% flexibility
                int toAllocate = Math.min(demand - alreadyAllocated, remainingCapacity);
                toAllocate = Math.min(toAllocate, (int)Math.ceil(demand * 1.1) - alreadyAllocated);

                if (toAllocate > 0) {
                    if (src.name.equals("Solar")) allocations[i].solar += toAllocate;
                    else if (src.name.equals("Hydro")) allocations[i].hydro += toAllocate;
                    else allocations[i].diesel += toAllocate;

                    remainingCapacity -= toAllocate;
                }
            }
        }
        return allocations;
    }
}
