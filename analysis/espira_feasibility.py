"""
ESPIRA feasibility check — first-order physics of electrostatic debris capture.

Questions answered:
  1. How far does an electric field reach in orbit? (plasma Debye screening, LEO vs GEO)
  2. How much charge / force can ESPIRA's ±20 kV system actually produce?
  3. Is that force enough to capture debris? (delta-v budget vs what is needed)
  4. MYCENET: how often would debris cross a 200 m filament web, and what happens when it does?

All models are standard first-order approximations (isolated-sphere capacitance,
Debye-screened Coulomb force as used in the electrostatic-tractor literature,
e.g. Schaub & Moorer 2012). They are meant to test orders of magnitude, not to
replace a full plasma/charging simulation (e.g. NASCAP-2k or SPIS).

Run:  python espira_feasibility.py      -> prints results, saves figures to ./figures
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------- constants ----------------
EPS0 = 8.854e-12          # F/m
KC = 1 / (4 * np.pi * EPS0)
QE = 1.602e-19            # C
ME = 9.109e-31            # kg
YEAR = 3.156e7            # s
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figures")
os.makedirs(OUT, exist_ok=True)


def debye_length(n_m3, T_eV):
    """Electron Debye length [m]."""
    return np.sqrt(EPS0 * T_eV * QE / (n_m3 * QE**2))


def sphere_charge(V, R, lam=np.inf):
    """Charge [C] on a sphere of radius R at potential V in a plasma with Debye length lam.
    Capacitance of a screened sphere: C = 4*pi*eps0*R*(1 + R/lam)."""
    return 4 * np.pi * EPS0 * R * (1 + R / lam) * V


def screened_force(Q1, Q2, d, lam):
    """Magnitude of Debye-screened Coulomb force [N] between two point-like charges at distance d.
    F = k Q1 Q2 / d^2 * (1 + d/lam) * exp(-d/lam)  (Schaub's electrostatic-tractor form)."""
    return KC * abs(Q1 * Q2) / d**2 * (1 + d / lam) * np.exp(-d / lam)


print("=" * 72)
print("1. HOW FAR DOES THE FIELD REACH?  (Debye length)")
print("=" * 72)
envs = {
    # name: (electron density m^-3, electron temperature eV)  — typical ranges
    "LEO 400-550 km, dense (day)":   (1e12, 0.2),
    "LEO 400-550 km, sparse (night)": (1e10, 0.1),
    "GEO quiet":                      (1e6, 1000.0),
    "GEO storm (hot, thin)":          (1e5, 10000.0),
}
lams = {}
for k, (n, T) in envs.items():
    lams[k] = debye_length(n, T)
    print(f"  {k:34s} lambda_D = {lams[k]:10.4f} m")
lam_leo_day = lams["LEO 400-550 km, dense (day)"]
lam_leo_night = lams["LEO 400-550 km, sparse (night)"]
lam_geo = lams["GEO quiet"]
print("  -> In LEO the plasma screens charge within millimetres-centimetres;")
print("     in GEO the field reaches hundreds of metres. LEO is NOT a vacuum for electrostatics.")

print()
print("=" * 72)
print("2. CHARGE AND FORCE FROM ESPIRA's ±20 kV SYSTEM")
print("=" * 72)
V = 20e3                 # ESPIRA V1 panels: ±20 kV
R_probe = 1.0            # m, effective radius of the probe body + panels
R_debris = 0.5           # m, a large debris object (e.g. defunct small satellite)
d = np.linspace(2, 200, 2000)

def cl_sheath(V, n, T_eV):
    """Child-Langmuir (planar) high-voltage sheath thickness [m] — order-of-magnitude.
    At kV potentials the sheath is far thicker than lambda_D, and inside it the field
    is roughly unscreened."""
    lam = debye_length(n, T_eV)
    return (np.sqrt(2) / 3) * lam * (2 * V / T_eV) ** 0.75


Qp_vac = sphere_charge(V, R_probe)
Qd_vac = sphere_charge(-V, R_debris)
F_vac = KC * abs(Qp_vac * Qd_vac) / d**2
results = {"Vacuum (upper bound)": F_vac,
           "GEO quiet (Debye-screened)": screened_force(Qp_vac, Qd_vac, d, lam_geo)}

V_ORB = 7.6e3   # m/s orbital speed (ram ion collection)
power_rows = []
for name, (n, T) in [("LEO day", envs["LEO 400-550 km, dense (day)"]),
                     ("LEO night", envs["LEO 400-550 km, sparse (night)"])]:
    s = cl_sheath(V, n, T)
    lam = debye_length(n, T)
    # inside the sheath: ~unscreened; outside: screened from the sheath edge
    F = np.where(d <= s, F_vac, KC * abs(Qp_vac * Qd_vac) / d**2 * np.exp(-np.clip(d - s, 0, None) / lam))
    results[f"{name} (sheath ~{s:.0f} m)"] = F
    # Current the probe must collect to hold -20 kV: ram ion flux into the sheath cross-section
    A = np.pi * (R_probe + s) ** 2
    I_ion = n * QE * V_ORB * A
    # Holding +20 kV collects electrons (thermal flux, ~ sqrt(mi/me) larger) — even worse
    I_e = n * QE * np.sqrt(T * QE / (2 * np.pi * ME)) * 4 * np.pi * (R_probe + s) ** 2
    power_rows.append((name, s, I_ion * V, I_e * V))

for name, F in results.items():
    i10, i50, i200 = np.argmin(abs(d - 10)), np.argmin(abs(d - 50)), np.argmin(abs(d - 200))
    print(f"  {name:30s} F(10 m)={F[i10]:.2e} N  F(50 m)={F[i50]:.2e} N  F(200 m)={F[i200]:.2e} N")
print(f"  Probe charge at 20 kV (R=1 m): {Qp_vac*1e6:.2f} uC")
print()
print("  Power needed just to HOLD the probe at 20 kV in LEO plasma (order of magnitude):")
for name, s, P_neg, P_pos in power_rows:
    print(f"    {name:10s} sheath ~{s:6.1f} m | at -20 kV: {P_neg/1e3:8.1f} kW | at +20 kV: {P_pos/1e3:10.1f} kW")
print("    ESPIRA solar array: 1.4 kW.  -> In LEO the limit is POWER, not range:")
print("    the plasma drains the charge faster than the array can replace it.")

F10_vac = F_vac[np.argmin(abs(d - 10))]

fig, ax = plt.subplots(figsize=(7, 4.2))
for name, F in results.items():
    Fp = np.where(F > 1e-30, F, np.nan)
    ax.semilogy(d, Fp, label=name, lw=2)
ax.set_ylim(1e-12, 1e-1)
ax.set_xlabel("Separation between probe and debris [m]")
ax.set_ylabel("Electrostatic force [N]")
ax.set_title("ESPIRA ±20 kV: force vs distance with plasma screening")
ax.axvline(10, color="grey", ls=":", lw=1)
ax.text(11, 2e-2, "V1 claimed\n10 m range", fontsize=8, color="grey")
ax.grid(alpha=0.3, which="both")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig1_force_vs_distance.png"), dpi=160)

print()
print("=" * 72)
print("3. IS THE FORCE ENOUGH?  (delta-v budget, best case = vacuum force at 10 m)")
print("=" * 72)
m_debris = 100.0   # kg (small defunct satellite)
F_best = F10_vac
for label, t in [("1 hour", 3600), ("1 day", 86400), ("30 days", 30 * 86400)]:
    dv = F_best * t / m_debris
    print(f"  Push {m_debris:.0f} kg debris for {label:8s}: delta-v = {dv:.3e} m/s")
needs = {
    "Stop a crossing fragment (relative speed)": 10_000.0,
    "Lower 550 km circular orbit to fast-decay perigee (~200 km)": 100.0,
    "GEO graveyard re-orbit (+300 km)": 11.0,
}
for k, v in needs.items():
    t_needed = v * m_debris / F_best
    print(f"  {k:62s} needs {v:>8.1f} m/s -> {t_needed/YEAR:10.2f} years of continuous push")
print("  -> Even ignoring plasma screening, electrostatic force at 10 m is ~mN-scale:")
print("     useful for slow, co-orbital nudging/detumbling (GEO tractor concept),")
print("     hopeless for capturing objects that are moving relative to the probe.")

print()
print("=" * 72)
print("4. MYCENET: encounter rate and what an encounter means")
print("=" * 72)
L_total = 9 * 200.0        # m of filament (9 strands x 200 m)
w_fil = 50e-6              # m filament diameter
v_rel = 10e3               # m/s typical LEO crossing speed
# Spatial densities at ~550-800 km (order of magnitude, from ESA MASTER-type models).
# NOTE: the V2 guide assumed 1 object per 1000 km^3 (=1e-3 /km^3) for trackable debris —
# about 4 orders of magnitude too high for >10 cm objects.
pops = {
    ">10 cm (guide's assumption)": (1e-3, 0.10),
    ">10 cm (realistic)":          (1e-7, 0.10),
    "1-10 cm":                     (3e-6, 0.03),
    "1 mm-1 cm":                   (3e-4, 0.003),
}
for k, (n_km3, size) in pops.items():
    sigma_m2 = L_total * (size + w_fil)          # swept cross-section of web for this size
    rate = n_km3 * 1e-9 * sigma_m2 * v_rel * YEAR  # per year
    print(f"  {k:30s} encounters/yr = {rate:9.3g}")
m_1cm = 2700 * (4 / 3) * np.pi * 0.005**3
KE = 0.5 * m_1cm * v_rel**2
W_es = F_best * 200
print(f"  Kinetic energy of a 1 cm Al sphere at 10 km/s: {KE/1e3:.0f} kJ")
print(f"  Work electrostatic field can do over 200 m (best case): {W_es:.2e} J")
print(f"  -> ratio {KE/W_es:.1e}: a crossing fragment cannot be slowed; it would cut the filament.")

# Figure 2: delta-v needed vs available
fig, ax = plt.subplots(figsize=(7, 3.6))
labels = ["Available:\n1 day push", "Available:\n30 day push", "Needed:\nGEO re-orbit",
          "Needed:\nLEO deorbit", "Needed:\nstop crossing\nfragment"]
vals = [F_best * 86400 / m_debris, F_best * 30 * 86400 / m_debris, 11, 100, 10000]
cols = ["#4C9F70", "#4C9F70", "#C0504D", "#C0504D", "#C0504D"]
ax.bar(labels, vals, color=cols)
ax.set_yscale("log")
ax.set_ylabel("delta-v [m/s] (100 kg debris)")
ax.set_title("Electrostatic push available vs. needed (best case, 10 m, no plasma)")
ax.grid(axis="y", alpha=0.3, which="both")
fig.tight_layout()
fig.savefig(os.path.join(OUT, "fig2_deltav_budget.png"), dpi=160)

print()
print("Figures saved to", OUT)
