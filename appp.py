import streamlit as st
import time
import plotly.graph_objects as go

st.set_page_config(page_title="Gravity Battery - Seesaw Simulation", layout="wide")

# ---------- CONFIG ----------
FRAME_DELAY = 0.08   # seconds per animation frame (lower = faster)
GRAVITY = 9.81      # m/s²
HEIGHT = 100        # m (from +50m to -50m)
B1_CAPACITY = 100_000  # Joules (100 kJ for Battery 1)
B2_CAPACITY = 1_000_000  # Joules (1 MJ for Battery 2)
STORAGE_THRESHOLD = 80  # kg to trigger big cycle
MAX_TOTAL_BLOCKS = 20  # Max blocks (200kg) at A and B combined

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

# ---------- DRAW / ANIMATION HELPERS ----------
def draw_scene(moving_blocks=None, note=""):
    """
    moving_blocks: None or list of tuples [(point_name, color, y, size_kg, label, block_index), ...]
    point_name: 'left'/'right'/'BIG'/'storage_left'/'storage_right'
    y: y coordinate of top of the moving rectangle
    size_kg: kg size for annotation (10, 20, or 160)
    label: "Dropping" or "Lifting"
    block_index: for storage blocks, indicates which 10kg block (for stacking)
    """
    fig = go.Figure()
    # Ground line
    fig.add_shape(type="line", x0=-3, y0=0, x1=3, y1=0, line=dict(color="black", width=3))
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

    # Moving blocks (dropping or lifting)
    if moving_blocks:
        for pt, color, y, size_kg, label, block_index in moving_blocks:
            if size_kg == 0:  # Skip if no block to animate
                continue
            if pt == "left":
                x0, x1 = -2.1, -1.5
                y_offset = y + block_index * 1.05  # Stack blocks during lift
            elif pt == "right":
                x0, x1 = 1.5, 2.1
                y_offset = y + block_index * 1.05
            elif pt == "BIG":
                x0, x1 = -1.2, 1.2
                y_offset = y
            elif pt == "storage_left":
                x0, x1 = -2.1, -1.5
                y_offset = y + block_index * 1.05
            elif pt == "storage_right":
                x0, x1 = 1.5, 2.1
                y_offset = y + block_index * 1.05
            else:
                x0, x1 = -0.6, 0.6
                y_offset = y
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y_offset, y1=y_offset + 0.95, fillcolor=color, line=dict(color="black"))
            fig.add_annotation(x=(x0 + x1) / 2, y=y_offset + 1.2, text=f"{label}: {size_kg}kg", showarrow=False)

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

def animate_seesaw(placeholder, drop_side, drop_color, lift_side, lift_color, drop_size=20, lift_size=10, steps=50):
    start_drop_y = 50
    end_drop_y = -50
    start_lift_y = -50
    end_lift_y = 50
    for step in range(steps):
        if st.session_state.stop_requested:
            st.session_state.logs.append("Animation stopped due to user request.")
            return False
        t = step / (steps - 1)
        drop_y = start_drop_y + (end_drop_y - start_drop_y) * t
        lift_y = start_lift_y + (end_lift_y - start_lift_y) * t if lift_size > 0 else None
        moving_blocks = [(drop_side, drop_color, drop_y, drop_size, "Dropping", 0)]
        if lift_size > 0:
            moving_blocks.append((lift_side, lift_color, lift_y, lift_size, "Lifting", 0))
        fig = draw_scene(moving_blocks=moving_blocks)
        placeholder.plotly_chart(fig, use_container_width=True)
        time.sleep(FRAME_DELAY)
    st.session_state.logs.append(f"Completed animation: Dropped {drop_size}kg from {drop_side}, Lifted {lift_size}kg to {lift_side}")
    return True

def animate_big_cycle(placeholder, storage_left, storage_right, steps=60):
    # First, simultaneous drop 160kg and lift storage blocks at C and D in parallel
    start_drop_y = 50
    end_drop_y = -50
    start_lift_y = -50
    end_lift_y = 50
    num_stored_left = storage_left // 10
    num_stored_right = storage_right // 10
    for step in range(steps):
        if st.session_state.stop_requested:
            st.session_state.logs.append("Big cycle animation stopped due to user request.")
            return False
        t = step / (steps - 1)
        drop_y = start_drop_y + (end_drop_y - start_drop_y) * t
        lift_y = start_lift_y + (end_lift_y - start_lift_y) * t
        moving_blocks = [
            ("BIG", "#805ad5", drop_y, 160, "Dropping", 0)
        ]
        # Add lifting storage blocks at C (left)
        for i in range(num_stored_left):
            moving_blocks.append(("storage_left", "#dd6b20", lift_y, 10, "Lifting", i))
        # Add lifting storage blocks at D (right)
        for i in range(num_stored_right):
            moving_blocks.append(("storage_right", "#dd6b20", lift_y, 10, "Lifting", i))
        fig = draw_scene(moving_blocks=moving_blocks)
        placeholder.plotly_chart(fig, use_container_width=True)
        time.sleep(FRAME_DELAY)
    st.session_state.logs.append(f"Completed simultaneous drop 160kg and parallel lift {storage_left}kg from C, {storage_right}kg from D")

    # Pause briefly
    time.sleep(0.4)

    # Then, lift 160kg back up
    start_lift_y = -50
    end_lift_y = 50
    for step in range(steps):
        if st.session_state.stop_requested:
            st.session_state.logs.append("Big cycle animation stopped due to user request.")
            return False
        t = step / (steps - 1)
        lift_y = start_lift_y + (end_lift_y - start_lift_y) * t
        moving_blocks = [
            ("BIG", "#805ad5", lift_y, 160, "Lifting", 0)
        ]
        fig = draw_scene(moving_blocks=moving_blocks)
        placeholder.plotly_chart(fig, use_container_width=True)
        time.sleep(FRAME_DELAY)
    st.session_state.logs.append("Completed lift 160kg back up")
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
        st.session_state.logs.append("Simulation started.")
    if st.button("Stop"):
        st.session_state.stop_requested = True
        st.session_state.running = False
        st.session_state.logs.append("Simulation stopped.")

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
    drop_color = None
    lift_color = None
    lifted = 0

    # Log state
    total_storage = st.session_state.storage_left + st.session_state.storage_right
    st.session_state.step_count += 1
    state_log = (
        f"--- Step {st.session_state.step_count - 1} ---\n"
        f"Top A: {st.session_state.blocks_top_A * 10}kg | Top B: {st.session_state.blocks_top_B * 10}kg\n"
        f"Tied C: {st.session_state.tied_bottom_C * 10}kg | Tied D: {st.session_state.tied_bottom_D * 10}kg\n"
        f"Storage L: {st.session_state.storage_left}kg | Storage R: {st.session_state.storage_right}kg | Total: {total_storage}kg\n"
        f"B1: {st.session_state.battery1}% | B2: {st.session_state.battery2}% | Gen: {st.session_state.generator_angle}°\n"
        f"Houses: {'lit' if st.session_state.houses_lit else 'dark'}"
    )
    st.session_state.logs.append(state_log)
    st.session_state.logs = st.session_state.logs[-100:]  # Limit to last 100 entries

    left_color = "#2b6cb0"
    right_color = "#c53030"

    # Check for drops
    try:
        if st.session_state.blocks_top_A == 2 and st.session_state.blocks_top_B < 2:
            lifted = st.session_state.tied_bottom_D
            ok = animate_seesaw(scene_ph, "left", left_color, "right", right_color, drop_size=20, lift_size=10 if lifted > 0 else 0)
            if not ok:
                st.session_state.stop_requested = True
            st.session_state.blocks_top_A = 0
            st.session_state.storage_left += 10
            st.session_state.tied_bottom_C += 1
            st.session_state.tied_bottom_D = 0
            st.session_state.blocks_top_B += lifted
            side, opposite, drop_color, lift_color = "left", "right", left_color, right_color
            dropped = True
        elif st.session_state.blocks_top_B == 2 and st.session_state.blocks_top_A < 2:
            lifted = st.session_state.tied_bottom_C
            ok = animate_seesaw(scene_ph, "right", right_color, "left", left_color, drop_size=20, lift_size=10 if lifted > 0 else 0)
            if not ok:
                st.session_state.stop_requested = True
            st.session_state.blocks_top_B = 0
            st.session_state.storage_right += 10
            st.session_state.tied_bottom_D += 1
            st.session_state.tied_bottom_C = 0
            st.session_state.blocks_top_A += lifted
            side, opposite, drop_color, lift_color = "right", "left", right_color, left_color
            dropped = True
        elif st.session_state.blocks_top_A == 2 and st.session_state.blocks_top_B == 2:
            # Alternate drops when both sides have 2 blocks
            if st.session_state.step_count % 2 == 0:
                lifted = st.session_state.tied_bottom_D
                ok = animate_seesaw(scene_ph, "left", left_color, "right", right_color, drop_size=20, lift_size=10 if lifted > 0 else 0)
                if not ok:
                    st.session_state.stop_requested = True
                st.session_state.blocks_top_A = 0
                st.session_state.storage_left += 10
                st.session_state.tied_bottom_C += 1
                st.session_state.tied_bottom_D = 0
                st.session_state.blocks_top_B += lifted
                side, opposite, drop_color, lift_color = "left", "right", left_color, right_color
            else:
                lifted = st.session_state.tied_bottom_C
                ok = animate_seesaw(scene_ph, "right", right_color, "left", left_color, drop_size=20, lift_size=10 if lifted > 0 else 0)
                if not ok:
                    st.session_state.stop_requested = True
                st.session_state.blocks_top_B = 0
                st.session_state.storage_right += 10
                st.session_state.tied_bottom_D += 1
                st.session_state.tied_bottom_C = 0
                st.session_state.blocks_top_A += lifted
                side, opposite, drop_color, lift_color = "right", "left", right_color, left_color
            dropped = True

        if not dropped:
            st.session_state.logs.append("No drop condition met, checking again...")
            time.sleep(0.2)
            st.rerun()

        # Generate power for small drop (20kg)
        if dropped:
            energy_joules = 20 * GRAVITY * HEIGHT  # 19,620 J
            st.session_state.battery1 = min(st.session_state.battery1 + (energy_joules / B1_CAPACITY) * 100, 100)
            st.session_state.generator_angle += (energy_joules / B1_CAPACITY) * 360  # Proportional rotation
            st.session_state.houses_lit = st.session_state.battery1 >= 10

            # Log drop event
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

        # Update scene after drop
        scene_ph.plotly_chart(draw_scene(), use_container_width=True)
        time.sleep(0.4)

        # Check for STORAGE threshold -> trigger BIG CYCLE
        total_storage = st.session_state.storage_left + st.session_state.storage_right
        if total_storage >= STORAGE_THRESHOLD:
            st.session_state.logs.append(f"Action: Big cycle triggered (Storage = {total_storage}kg). Dropping 160kg...")
            ok = animate_big_cycle(scene_ph, st.session_state.storage_left, st.session_state.storage_right)
            if not ok:
                st.session_state.stop_requested = True
            energy_joules = 160 * GRAVITY * HEIGHT  # 156,960 J
            st.session_state.generator_angle += (energy_joules / B2_CAPACITY) * 360
            st.session_state.battery2 = min(st.session_state.battery2 + (energy_joules / B2_CAPACITY) * 100, 100)
            
            # Redistribute storage blocks to A and B
            total_blocks_to_distribute = (st.session_state.storage_left + st.session_state.storage_right) // 10
            blocks_to_a = total_blocks_to_distribute // 2
            blocks_to_b = total_blocks_to_distribute - blocks_to_a
            # Ensure we don't exceed MAX_TOTAL_BLOCKS
            available_slots = MAX_TOTAL_BLOCKS - (st.session_state.blocks_top_A + st.session_state.blocks_top_B)
            blocks_to_a = min(blocks_to_a, available_slots)
            blocks_to_b = min(blocks_to_b, available_slots - blocks_to_a)
            st.session_state.blocks_top_A += blocks_to_a
            st.session_state.blocks_top_B += blocks_to_b
            st.session_state.storage_left = 0
            st.session_state.storage_right = 0
            st.session_state.battery2 = max(st.session_state.battery2 - (80_000 / B2_CAPACITY) * 100, 0)  # Assume 80 kJ to lift 160kg
            
            total_storage = st.session_state.storage_left + st.session_state.storage_right
            st.session_state.logs.append(
                f"--- Step {st.session_state.step_count} ---\n"
                f"Top A: {st.session_state.blocks_top_A * 10}kg | Top B: {st.session_state.blocks_top_B * 10}kg\n"
                f"Tied C: {st.session_state.tied_bottom_C * 10}kg | Tied D: {st.session_state.tied_bottom_D * 10}kg\n"
                f"Storage L: {st.session_state.storage_left}kg | Storage R: {st.session_state.storage_right}kg | Total: {total_storage}kg\n"
                f"B1: {st.session_state.battery1}% | B2: {st.session_state.battery2}% | Gen: {st.session_state.generator_angle}°\n"
                f"Houses: {'lit' if st.session_state.houses_lit else 'dark'}\n"
                f"Action: Big cycle: Dropped 160kg, lifted {total_blocks_to_distribute * 10}kg in parallel (C: {blocks_to_a * 10}kg to A, D: {blocks_to_b * 10}kg to B), "
                f"B2 +{(energy_joules / B2_CAPACITY) * 100:.1f}%, Gen +{(energy_joules / B2_CAPACITY) * 360:.0f}°. "
                f"Reset storages. Used {(80_000 / B2_CAPACITY) * 100:.1f}% B2 to lift 160kg."
            )
            st.session_state.logs = st.session_state.logs[-100:]
            st.session_state.houses_lit = st.session_state.battery1 >= 10
            scene_ph.plotly_chart(draw_scene(), use_container_width=True)
            time.sleep(0.6)

        # Rerun to update UI with new values
        st.rerun()

    except Exception as e:
        st.session_state.logs.append(f"Error in simulation step: {str(e)}")
        st.session_state.stop_requested = True
        st.rerun()

# Event Log display
st.subheader("Simulation Steps & Events")
st.text_area("Simulation Log", value="\n".join(st.session_state.logs), height=300, disabled=True)
