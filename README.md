# Flamewave

A participant-interactive kinetic fire sculpture for Burning Man. Two arms of
flexible conduit carry propane gas that leaks through threaded couplings,
creating a distributed "flaming rope" effect. Participants on each side pull a
chain to send waves of fire undulating along the arms. When the two arms
synchronize, a poofer fires at the center.

---

## Concept

The sculpture runs roughly 20 feet wide, installed in a camp fire garden along
the esplanade. The conduit arms are elevated overhead, running parallel to the
ground, so participants stand beneath a pair of undulating fire ropes and look
up at the wave action.

The central mechanic is synchronization: two strangers, one on each side, have
to find the same rhythm to trigger the poofer. The sculpture rewards
coordination without requiring communication — the fire itself is the feedback.

---

## Physical Design

### Overview

```
[spring/chain]~~~~~~~~~[slider]~~~~~~~~~[spring/chain]
      \                   |                   /
       \              [POOFER]               /
        \            center post            /
         \                                 /
          \                               /
       outer post                     outer post
```

Two 3/4" EMT conduit arms extend outward and downward from a center post at
approximately 15–20 degrees below horizontal. The center post is the high point
of the structure, with the poofer head at 10 feet (meeting the Burning Man 10'
rule for poofer clearance). The outer ends drop to roughly 7 feet, putting the
chain pull at a comfortable reach height for participants.

### Dimensions

| Parameter | Value |
|---|---|
| Total span | ~20 ft (two 10 ft arms) |
| Center attach height | 9 ft |
| Poofer height | 10 ft |
| Arm drop angle | 15–20° (adjustable) |
| Outer end height | ~6.9 ft at 17.5° |
| Chain bottom | ~2.4 ft off ground |

### Conduit Arms

**Material:** 3/4" EMT (electrical metallic conduit)

- OD: 0.922"
- Weight: ~0.85 lb/ft; each 10 ft arm ~8.5 lbs before fittings

**Flame effect:** Standard threaded couplings left slightly loose at each
joint. Propane leaks from the gaps and ignites, creating discrete flame jets at
each coupling. More segments per arm = more couplings = denser fire. The
default design uses 4 sticks per arm (3 coupling/flame points per arm, 6
total).

3/4" EMT is flexible enough over a 10 ft span to support visible wave
propagation while providing enough cross-section for adequate gas flow and
flame intensity along the full run.

### Center Post

- Single vertical post driven into the playa, anchored with a ground plate and
  lag bolts
- Poofer head at 10 ft
- Carries the center slider assembly (see below)
- Houses the solenoid valve and wiring

### Outer Posts

One outer post per arm, positioned at each end of the sculpture. Each post
carries a spring anchor point above the conduit end level. The spring hangs in
tension from the anchor, connecting down to the conduit end and chain
attachment point.

---

## Kinetic Mechanism

### Wave Generation

The chain attaches at the junction between the spring and the conduit end —
the outer tip of each arm. Participants pull the chain downward, displacing the
conduit tip. The spring snaps it back. This impulse propagates as a transverse
wave along the conduit toward the center, with amplitude building toward the
floating tip (similar to cracking a whip).

### Center Slider

Both floating conduit tips (the inner ends, near the center post) attach to a
shared sliding carriage on the center post. The carriage rides on a vertical
rail or rod and is free to travel up and down.

This coupling is the key mechanical insight: the slider acts as a passive
synchronization detector.

- **Anti-phase oscillation** (one tip up, one down): forces at the carriage
  cancel. The slider barely moves. The poofer does not fire.
- **In-phase oscillation** (both tips moving together): forces at the carriage
  add. The slider swings to its travel limit, trips the trigger switch, and
  fires the poofer.

This is an instance of the Huygens synchronization effect — two oscillators
coupled through a shared structure tend to phase-lock over time. Participants
on opposite sides will naturally find the synchronized rhythm through the
feedback of increasing flame motion, culminating in the poofer firing when they
lock in.

### Slider Design Considerations

- **Rail material:** steel rod or tube on the center post with a UHMW
  (ultra-high-molecular-weight polyethylene) bushing on the carriage for
  low-friction, dust-tolerant sliding. Avoid ball bearings — playa dust will
  destroy them.
- **Tip attachment compliance:** A short loose pin-in-slot or small flex
  connection between each conduit tip and the carriage allows the arms some
  independent character while preserving the coupling effect through the
  carriage mass. Fully rigid attachment forces identical motion and may feel
  less interesting to participants.
- **Return:** Gravity return to neutral (carriage falls to rest position when
  no energy input) is simplest. A light spring return is an option if you want
  a defined neutral position.

---

## Trigger & Fire Control

### Mechanical Limit Switch

One weatherproof roller-lever limit switch (e.g. Honeywell BZLD series, IP67)
mounted at the top of the slider travel on the center post. When the carriage
reaches the trigger height it contacts the roller and closes the circuit.

A single switch is sufficient — the slider reaching its travel limit already
encodes the synchronization condition. No logic controller needed.

### Wiring

```
[12V supply] ── [limit switch (NO)] ── [solenoid valve] ── [GND]
```

- Normally-open switch: circuit open at rest, closes when carriage trips lever
- Solenoid valve: 12V DC, controls propane flow to the poofer
- Supply: sealed 12V battery or regulated supply in a weatherproof enclosure

### Poofer

- Mounted at top of center post at 10 ft (meets Burning Man 10' rule)
- Nozzle points vertically upward
- Fed by the solenoid valve; propane supply line runs down the center post
- A pilot light or continuous igniter is needed — the coupling joints on the
  arms stay lit, but the poofer needs its own ignition source

### Switch Mounting

The switch bracket attaches to the center post with a slotted hole for height
adjustment. Adjust the trigger height on-site to tune how much slider travel
(i.e. how well-synchronized the arms need to be) is required to fire. Higher
trigger position = arms must be more precisely in phase = harder to achieve but
more dramatic payoff.

---

## Propane Plumbing

*(To be detailed — this section is a placeholder)*

- Regulator at supply tank
- Flex hose from regulator to center post manifold
- Hard line or armored flex down each arm to the far end
- Gas enters the conduit at the outer (spring) end and flows toward center
- Pressure TBD based on coupling gap size and desired flame height
- Ball valve for manual shutoff at the tank; solenoid valve for poofer only

---

## Safety Notes

- 10 ft clearance rule met by poofer placement
- Flaming rope arms are elevated overhead; flame jets point upward, away from
  participants
- All propane connections pressure-tested before event
- Manual shutoff accessible at the tank
- Fire safety officer briefed on shutoff location
- No official Burning Man placement — installed in camp fire garden under camp
  safety protocols

---

## Files

| File | Description |
|---|---|
| `flamewave_gen.py` | Blender Python script — generates the full 3D geometry |

### Using the Blender Generator

1. Open Blender (3.x or 4.x)
2. Go to the **Scripting** workspace
3. Open `flamewave_gen.py`
4. Click **Run Script**

The scene generates with camera and lighting set for a three-quarter view
render. Adjust parameters at the top of the file:

```python
ARM_LENGTH_FT    = 10.0   # each arm length in feet
ARM_ANGLE_DEG    = 17.5   # drop angle (try 15–20)
SEGMENTS_PER_ARM = 4      # EMT sticks per arm; more = more flame points
SPRING_LENGTH_FT = 1.0    # spring free length at outer end
CHAIN_LENGTH_FT  = 4.5    # chain hanging length
```

Re-run the script after any parameter change to regenerate the scene from
scratch.

---

## Status

Early design phase. Key open items:

- [ ] Slider carriage mechanical design (rail type, bushing, travel length)
- [ ] Conduit tip to carriage attachment detail (rigid vs. compliant)
- [ ] Propane plumbing layout and pressure spec
- [ ] Poofer ignition method
- [ ] Outer post structural design and ground anchoring
- [ ] Spring selection (rate, length, load capacity)
- [ ] Electrical enclosure and wiring harness
- [ ] Transport and assembly plan
