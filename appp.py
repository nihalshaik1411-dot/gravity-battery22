import streamlit as st
import time
import plotly.graph_objects as go
import numpy as np

st.set_page_config(page_title="Gravity Battery - Seesaw Simulation", layout="wide")

# ---------- CONFIG ----------
FRAME_DELAY = 0.08   # seconds per animation frame (lower = faster)
GRAVITY = 9.81      # m/s²
HEIGHT = 100        # m (from +50m to -50m)
B1_CAPACITY = 100_000  # Joules (100 kJ for Battery 1)
B2_CAPACITY = 1_000_000  # Joules (1 MJ for Battery 2)
STORAGE_THRESHOLD = 80  # kg to trigger big cycle
MAX_TOTAL_BLOCKS = 20  # Max blocks (200kg) at A and B combined
POWER_CONSUMPTION_RATE = 2_000  # Joules per step (2 kJ/step)
LIFT_ENERGY_EFFICIENCY = 0.5  # Efficiency of lifting blocks with stored energy

# ---------- SESSION STATE ----------
if "blocks_top_A" not in st.session_state:
    st.session_state.blocks_top_A = 1  # initial 10 kg = 1 block
if "blocks_top_B" not in st.session_state:
    st.session_state.blocks_top_B = 2  # initial 20 kg = 2 blocks
if "tied_bottom_C" not in st.session_state:
    st.session_state.tied_bottom_C = 0
if "tied_bottom_D" not in st.session_state:
    st.session_state.tied_bottom_D = 0
if "storage_left" not in st.session_state:
    st.session_state.storage_left = 0
if "storage_right" not in st.session_state:
    st.session_state.storage_right = 0
if "battery1" not in st.session_state:
    st.session_state.battery1 = 0  # small battery % (0-100)
if "battery2" not in st.session_state:
    st.session_state.battery2 = 0  # big battery % (0-100)
if "generator_angle" not in st.session_state:
    st.session_state.generator_angle = 0
if "houses_lit" not in st.session_state:
    st.session_state.houses_lit = False
if "running" not in st.session_state:
    st.session_state.running = False
if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False
if "logs" not in st.session_state:
    st.session_state.logs = []
if "step_count" not in st.session_state:
    st.session_state.step_count = 0
if "last_drop_side" not in st.session_state:
    st.session_state.last_drop_side = None

# ---------- DRAW / ANIMATION HELPERS ----------
def draw_scene(dropping=None, drop_y=None, dropping_size=10, note=""):
    """
    dropping: None or tuple(point_name e.g. 'left'/'right'/'BIG', color)
    drop_y: y coordinate of top of the falling rectangle
    dropping_size: kg size for annotation (20 or 160)
    """
    fig = go.Figure()

    # Determine seesaw angle based on which side is heavier
    angle = 0
    if st.session_state.blocks_top_A > st.session_state.blocks_top_B:
        angle = 5
    elif st.session_state.blocks_top_B > st.session_state.blocks_top_A:
        angle = -5
    
    # Draw seesaw
    pivot_x, pivot_y = 0, -50
    lever_length = 4.0
    lever_x = [-lever_length/2, lever_length/2]
    lever_y = [pivot_y - lever_length/2 * np.tan(np.deg2rad(angle)), pivot_y + lever_length/2 * np.tan(np.deg2rad(angle))]
    fig.add_shape(type="line", x0=-2, y0=-5, x1=2, y1=-5, line=dict(color="black", width=3))
    fig.add_shape(type="line", x0=-2, y0=5, x1=2, y1=5, line=dict(color="black", width=3))

    # Ground line
    fig.add_shape(type="line", x0=-3, y0=-50, x1=3, y1=-50, line=dict(color="black", width=3))
    # Labels for points
    fig.add_annotation(x=-1.8, y=55, text="A (+50m)", showarrow=False, font=dict(size=12))
    fig.add_annotation(x=1.8, y=55, text="B (+50m)", showarrow=False, font=dict(size=12))
    fig.add_annotation(x=-1.8, y=-55, text="C (−50m)", showarrow=False, font=dict(size=12))
    fig.add_annotation(x=1.8, y=-55, text="D (−50m)", showarrow=False, font=dict(size=12))

    # Draw stacked blocks at top A (left, blue)
    for i in range(st.session_state.blocks_top_A):
        y0 = 50 + i * 1.05
        fig.add_shape(type="rect", x0=-2.1, x1=-1.5, y0=y0, y1=y0 + 0.95, fillcolor="#2b6cb0", line=dict(color="black"))
    # Draw stacked blocks at top B (right, red)
    for i in range(st.session_state.blocks_top_B):
        y0 = 50 + i * 1.05
        fig.add_shape(type="rect", x0=1.5, x1=2.1, y0=y0, y1=y0 + 0.95, fillcolor="#c53030", line=dict(color="black"))

    # Tied block at bottom C (left, gray if present)
    if st.session_state.tied_bottom_C > 0:
        fig.add_shape(type="rect", x0=-2.1, x1=-1.5, y0=-51, y1=-50.05, fillcolor="gray", line=dict(color="black"))
    # Tied block at bottom D (right, gray if present)
    if st.session_state.tied_bottom_D > 0:
        fig.add_shape(type="rect", x0=1.5, x1=2.1, y0=-51, y1=-50.05, fillcolor="gray", line=dict(color="black"))

    # Stored blocks at left (below tied, orange)
    num_stored_left = st.session_state.storage_left // 10
    base_y_left = -51.05
    for i in range(num_stored_left):
        y1 = base_y_left - i * 1.05
        y0 = y1 - 0.95
        fig.add_shape(type="rect", x0=-2.1, x1=-1.5, y0=y0, y1=y1, fillcolor="#dd6b20", line=dict(color="black"))
    # Stored blocks at right (below tied, orange)
    num_stored_right = st.session_state.storage_right // 10
    base_y_right = -51.05
    for i in range(num_stored_right):
        y1 = base_y_right - i * 1.05
        y0 = y1 - 0.95
        fig.add_shape(type="rect", x0=1.5, x1=2.1, y0=y0, y1=y1, fillcolor="#dd6b20", line=dict(color="black"))

    # Optional dropping block
    if dropping and drop_y is not None:
        pt, color = dropping
        if pt == "left":
            x0, x1 = -2.1, -1.5
        elif pt == "right":
            x0, x1 = 1.5, 2.1
        elif pt == "BIG":
            x0, x1 = -1.2, 1.2
        else:
            x0, x1 = -0.6, 0.6
        fig.add_shape(type="rect", x0=x0, x1=x1, y0=drop_y, y1=drop_y + 0.95, fillcolor=color, line=dict(color="black"))
        fig.add_annotation(x=0, y=drop_y + 1.2, text=f"Dropping: {dropping_size}kg", showarrow=False)

    # Generator visual and angle
    angle = st.session_state.generator_angle % 360
    fig.add_shape(type="circle", x0=-0.4, y0=-20.6, x1=0.4, y1=-21.6, line=dict(color="orange", width=3))
    fig.add_annotation(x=0, y=-21.1, text=f"⚙ {angle:.0f}°", showarrow=False, font=dict(color="orange"))

    # Battery labels
    fig.add_annotation(x=-2.7, y=45, text=f"🔋 B1: {st.session_state.battery1:.0f}%", showarrow=False)
    fig.add_annotation(x=2.7, y=45, text=f"🔋 B2: {st.session_state.battery2:.0f}%", showarrow=False)

    # Houses indicator
    houses_text = "🏠 lit" if st.session_state.houses_lit else "🏠 dark"
    fig.add_annotation(x=0, y=45, text=houses_text, showarrow=False)

    fig.update_xaxes(visible=False, range=[-4, 4])
    fig.update_yaxes(visible=False, range=[-65, 65])
    fig.update_layout(height=600, margin=dict(l=10, r=10, t=10, b=10), autosize=True)
    return fig

def animate_fall(placeholder, pt, color="#2b6cb0", start_y=50, end_y=-50, steps=50, size_kg=20):
    for step in range(steps):
        if st.session_state.stop_requested:
            return False
        t = step / (steps - 1)
        y = start_y + (end_y - start_y) * t
        fig = draw_scene(dropping=(pt, color), drop_y=y, dropping_size=size_kg)
        placeholder.plotly_chart(fig, use_container_width=True)
        time.sleep(FRAME_DELAY)
    return True

# ---------- MAIN UI ----------
st.title("⚡ Gravity Battery — Seesaw Continuous Simulation")

left_col, mid_col, right_col = st.columns([1, 2, 1])

with left_col:
    st.subheader("Controls")
    if st.button("Start"):
        st.session_state.running = True
        st.session_state.stop_requested = False
        st.session_state.logs = []
        st.session_state.step_count = 0
        st.session_state.battery1 = 0
        st.session_state.battery2 = 0
        st.session_state.storage_left = 0
        st.session_state.storage_right = 0
        st.session_state.tied_bottom_C = 0
        st.session_state.tied_bottom_D = 0
    if st.button("Stop"):
        st.session_state.stop_requested = True
        st.session_state.running = False

    st.write("Initial top stacks (editable, max 200kg total):")
    blocks_a = st.number_input("Blocks at top A (10kg each)", min_value=0, max_value=MAX_TOTAL_BLOCKS, value=st.session_state.blocks_top_A, step=1)
    blocks_b = st.number_input("Blocks at top B (10kg each)", min_value=0, max_value=MAX_TOTAL_BLOCKS, value=st.session_state.blocks_top_B, step=1)
    if blocks_a + blocks_b <= MAX_TOTAL_BLOCKS:
        st.session_state.blocks_top_A = blocks_a
        st.session_state.blocks_top_B = blocks_b
    else:
        st.error(f"Total blocks (A + B) must not exceed {MAX_TOTAL_BLOCKS} (200kg).")

with mid_col:
    scene_ph = st.empty()

with right_col:
    st.subheader("Status")
    total_storage = st.session_state.storage_left + st.session_state.storage_right
    total_mass = (st.session_state.blocks_top_A + st.session_state.blocks_top_B +
                  st.session_state.tied_bottom_C + st.session_state.tied_bottom_D +
                  st.session_state.storage_left // 10 + st.session_state.storage_right // 10) * 10
    st.write(f"Step: {st.session_state.step_count}")
    st.write(f"Top A: {st.session_state.blocks_top_A * 10} kg")
    st.write(f"Top B: {st.session_state.blocks_top_B * 10} kg")
    st.write(f"Tied at C: {st.session_state.tied_bottom_C * 10} kg")
    st.write(f"Tied at D: {st.session_state.tied_bottom_D * 10} kg")
    st.write(f"Storage left (C): {st.session_state.storage_left} kg")
    st.write(f"Storage right (D): {st.session_state.storage_right} kg")
    st.write(f"Total storage: {total_storage} kg")
    st.write(f"Total mass: {total_mass} kg")
    st.write(f"Battery B1: {st.session_state.battery1:.0f}%")
    st.write(f"Battery B2: {st.session_state.battery2:.0f}%")
    st.write(f"Generator angle: {st.session_state.generator_angle:.0f}°")
    if st.session_state.houses_lit:
        st.success("Houses are lit by B1!")
    else:
        st.info("Houses are not lit yet")

# Render initial scene
scene_ph.plotly_chart(draw_scene(), use_container_width=True)

# ---------- SIMULATION STEP ----------
if st.session_state.running and not st.session_state.stop_requested:
    dropped = False
    side = None
    opposite = None
    color = None
    lifted = 0

    # Consume power from B1 first, then B2
    consumed_energy = POWER_CONSUMPTION_RATE
    if st.session_state.battery1 > 0:
        b1_joules = (st.session_state.battery1 / 100) * B1_CAPACITY
        if b1_joules >= consumed_energy:
            st.session_state.battery1 = st.session_state.battery1 - (consumed_energy / B1_CAPACITY) * 100
        else:
            st.session_state.battery1 = 0
            remaining_consumption = consumed_energy - b1_joules
            st.session_state.battery2 = max(st.session_state.battery2 - (remaining_consumption / B2_CAPACITY) * 100, 0)
    else:
        st.session_state.battery2 = max(st.session_state.battery2 - (consumed_energy / B2_CAPACITY) * 100, 0)

    st.session_state.houses_lit = st.session_state.battery1 > 0 or st.session_state.battery2 > 0

    # Log state
    total_storage = st.session_state.storage_left + st.session_state.storage_right
    st.session_state.step_count += 1
    state_log = (
        f"--- Step {st.session_state.step_count} ---\n"
        f"Top A: {st.session_state.blocks_top_A * 10}kg | Top B: {st.session_state.blocks_top_B * 10}kg\n"
        f"Tied C: {st.session_state.tied_bottom_C * 10}kg | Tied D: {st.session_state.tied_bottom_D * 10}kg\n"
        f"Storage L: {st.session_state.storage_left}kg | Storage R: {st.session_state.storage_right}kg | Total: {total_storage}kg\n"
        f"B1: {st.session_state.battery1:.1f}% | B2: {st.session_state.battery2:.1f}% | Gen: {st.session_state.generator_angle:.0f}°\n"
        f"Houses: {'lit' if st.session_state.houses_lit else 'dark'}"
    )
    st.session_state.logs.append(state_log)
    st.session_state.logs = st.session_state.logs[-100:]  # Limit to last 100 entries

    # Check for drops
    if st.session_state.blocks_top_A >= 2 and st.session_state.blocks_top_B < 2:
        ok = animate_fall(scene_ph, "left", color="#2b6cb0", steps=50, size_kg=20)
        if not ok: st.session_state.stop_requested = True
        st.session_state.blocks_top_A -= 2
        st.session_state.storage_left += 10
        st.session_state.tied_bottom_C += 1
        lifted = st.session_state.tied_bottom_D
        st.session_state.blocks_top_B += lifted
        st.session_state.tied_bottom_D = 0
        side, opposite, color = "left", "right", "#2b6cb0"
        st.session_state.last_drop_side = "left"
        dropped = True
    elif st.session_state.blocks_top_B >= 2 and st.session_state.blocks_top_A < 2:
        ok = animate_fall(scene_ph, "right", color="#c53030", steps=50, size_kg=20)
        if not ok: st.session_state.stop_requested = True
        st.session_state.blocks_top_B -= 2
        st.session_state.storage_right += 10
        st.session_state.tied_bottom_D += 1
        lifted = st.session_state.tied_bottom_C
        st.session_state.blocks_top_A += lifted
        st.session_state.tied_bottom_C = 0
        side, opposite, color = "right", "left", "#c53030"
        st.session_state.last_drop_side = "right"
        dropped = True
    elif st.session_state.blocks_top_A >= 2 and st.session_state.blocks_top_B >= 2:
        # Alternate drops when both sides have 2+ blocks
        if st.session_state.last_drop_side == "right":
            ok = animate_fall(scene_ph, "left", color="#2b6cb0", steps=50, size_kg=20)
            if not ok: st.session_state.stop_requested = True
            st.session_state.blocks_top_A -= 2
            st.session_state.storage_left += 10
            st.session_state.tied_bottom_C += 1
            lifted = st.session_state.tied_bottom_D
            st.session_state.blocks_top_B += lifted
            st.session_state.tied_bottom_D = 0
            side, opposite, color = "left", "right", "#2b6cb0"
            st.session_state.last_drop_side = "left"
        else:
            ok = animate_fall(scene_ph, "right", color="#c53030", steps=50, size_kg=20)
            if not ok: st.session_state.stop_requested = True
            st.session_state.blocks_top_B -= 2
            st.session_state.storage_right += 10
            st.session_state.tied_bottom_D += 1
            lifted = st.session_state.tied_bottom_C
            st.session_state.blocks_top_A += lifted
            st.session_state.tied_bottom_C = 0
            side, opposite, color = "right", "left", "#c53030"
            st.session_state.last_drop_side = "right"
        dropped = True

    if dropped:
        # Generate power for small drop (20kg)
        energy_joules = 20 * GRAVITY * HEIGHT
        st.session_state.battery1 = min(st.session_state.battery1 + (energy_joules / B1_CAPACITY) * 100, 100)
        st.session_state.generator_angle += (energy_joules / B1_CAPACITY) * 360
        
        lift_to = "B" if opposite == "right" else "A"
        drop_to = "C" if side == "left" else "D"
        st.session_state.logs.append(
            f"Action: Dropped 20kg from {side.upper()} to {drop_to}, stored 10kg, tied 10kg. "
            f"Lifted {lifted * 10}kg to {lift_to}. B1 +{(energy_joules / B1_CAPACITY) * 100:.1f}%, Generator +{(energy_joules / B1_CAPACITY) * 360:.0f}°."
        )
        # Add 10kg to opposite side
        if opposite == "left":
            st.session_state.blocks_top_A += 1
            add_side = "A"
        else:
            st.session_state.blocks_top_B += 1
            add_side = "B"
        st.session_state.logs.append(f"Action: Added 10kg to {add_side}.")
        st.session_state.logs = st.session_state.logs[-100:]
        
        scene_ph.plotly_chart(draw_scene(), use_container_width=True)
        time.sleep(0.4)

    # Check for STORAGE threshold -> trigger BIG CYCLE
    total_storage = st.session_state.storage_left + st.session_state.storage_right
    if total_storage >= STORAGE_THRESHOLD:
        st.session_state.logs.append(f"Action: Big cycle triggered (Storage = {total_storage}kg). Dropping 160kg...")
        ok = animate_fall(scene_ph, "BIG", color="#805ad5", steps=60, size_kg=160)
        if not ok: st.session_state.stop_requested = True
        
        # Power generation from dropping stored blocks
        energy_generated = total_storage * GRAVITY * HEIGHT
        st.session_state.battery2 = min(st.session_state.battery2 + (energy_generated / B2_CAPACITY) * 100, 100)
        st.session_state.generator_angle += (energy_generated / B2_CAPACITY) * 360

        # Power cost to lift all blocks back to the top
        lift_energy_cost = (total_storage * GRAVITY * HEIGHT) / LIFT_ENERGY_EFFICIENCY
        st.session_state.battery2 = max(st.session_state.battery2 - (lift_energy_cost / B2_CAPACITY) * 100, 0)
        
        st.session_state.storage_left = 0
        st.session_state.storage_right = 0
        st.session_state.logs.append(
            f"--- Big Cycle ---"
            f"Dropped {total_storage}kg. B2 gained {((energy_generated / B2_CAPACITY) * 100):.1f}%, cost {((lift_energy_cost / B2_CAPACITY) * 100):.1f}%."
        )
        st.session_state.logs = st.session_state.logs[-100:]
        scene_ph.plotly_chart(draw_scene(), use_container_width=True)
        time.sleep(0.6)

    # Rerun to update UI with new values
    if not st.session_state.stop_requested:
        st.rerun()

# Event Log display
st.subheader("Simulation Steps & Events")
st.text_area("Simulation Log", value="\n".join(st.session_state.logs), height=300, disabled=True)
