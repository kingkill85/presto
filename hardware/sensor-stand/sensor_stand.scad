// Sensor stand for the Presto desk: Adafruit VL53L1X (PID 3967) upright and
// facing forward, Soldered APDS-9960 easyC breakout lying flat beside it
// (swipe over it). The cables disappear into a hollow tray.
//
// Two parts, both print flat side down without supports:
//   tray  hollow box, cable exit at the back, four screw posts
//   deck  lid that drops into the tray's rim; carries both sensors. The ToF
//         sits in the bay of a hollow U: the (stiff) cables leave its sockets
//         straight sideways into the cheeks and bend down inside them. The
//         APDS uses only the socket facing the ToF; a long slot beside it
//         leaves room for a wide bend down into the tray.
// Render one part with:  openscad -D 'part="tray"' -o tray.stl sensor_stand.scad
//
// Board data from the vendors' PCB files:
//   VL53L1X  25.4 x 17.78 mm, 4 holes 2.5 mm at 2.54 mm from each corner,
//            sensor centred, STEMMA QT sockets centred on the short edges,
//            header row 2.54 mm above the long bottom edge.
//   APDS9960 22 x 38 mm, 2 holes 3.2 mm at (3, 3) and (3, 35) from one corner
//            (both on the same long edge), sensor centred, easyC sockets
//            centred on the long edges, headers 1.5 mm from both short edges.
//
// Screws (self-tapping into plastic): 4x M2.5 x 6 (ToF), 2x M3 x 8 (APDS),
// 4x M3 x 8 (deck into tray).
// Coordinates: x right, y back (front is y = 0), z up.

part = "assembly";  // "tray", "deck" or "assembly"

$fn = 40;

// --- parameters ---------------------------------------------------------------
W = 120;          // outer width
D = 60;           // outer depth
H = 18;           // tray height; the deck's top is flush with its rim
R = 4;            // corner radius
wall = 3;
floor_t = 2;
rim = 1.2;        // thin upper part of the wall the deck drops into
deck_t = 3;
fit = 0.25;       // clearance around the deck

tof_lift = 10;    // ToF board bottom edge above the deck
tof_gap = 4;      // standoffs in front of the U's back wall
u_x = wall + 2;   // left edge of the U
u_back = 26;      // front face of the U's back block (where the ToF sits)
u_depth = 14;     // back block depth
u_wall = 2;
plug_reach = 7;   // a JST-SH plug's body beyond the board edge
cheek_w = 14;     // hollow cheeks the cables bend down in
cable_hole = 9;   // square hole in each cheek, centred on the socket

apds_gap = 6;     // standoffs under the APDS
apds_slot = 17;   // slot beside the APDS socket for the cable's bend
m25_pilot = 2.2;
m3_pilot = 2.7;
m3_clear = 3.4;

exit_w = 12;      // cable exit at the back
exit_h = 7;

// --- boards ---------------------------------------------------------------------
TOF_W = 25.4; TOF_H = 17.78; TOF_HOLE = 2.54;
APDS_W = 22; APDS_L = 38;
APDS_HOLES = [[3, 3], [3, 35]];   // on the socket side used here
APDS_SUPPORT = [[19, 19]];
APDS_SOCKET_Y = 19;

tof_x = u_x + cheek_w + plug_reach;         // ToF board left edge
bay_l = tof_x - plug_reach;
bay_r = tof_x + TOF_W + plug_reach;
u_r = bay_r + cheek_w;
tof_front = u_back - tof_gap - 1.6;         // component side of the ToF board
socket_y = tof_front - 1.5;                 // plug centre in front of the board
socket_z = deck_t + tof_lift + TOF_H / 2;
u_front = socket_y - cable_hole / 2 - u_wall - 1;
u_top = socket_z + cable_hole / 2 + 8;
apds_x = u_r + 1 + apds_slot;
apds_y = (D - APDS_L) / 2;
ledge_z = H - deck_t;
post = [[wall + 4, wall + 4], [W - wall - 4, wall + 4],
        [wall + 4, D - wall - 4], [W - wall - 4, D - wall - 4]];

module rounded_box(w, d, h, r) {
    hull() for (x = [r, w - r], y = [r, d - r])
        translate([x, y, 0]) cylinder(r = r, h = h);
}

module standoff(h, d, pilot) {
    difference() {
        cylinder(d = d, h = h);
        translate([0, 0, -1]) cylinder(d = pilot, h = h + 2);
    }
}

// --- tray -----------------------------------------------------------------------
module tray() {
    difference() {
        rounded_box(W, D, H, R);
        // Cavity below the ledge, then the wider pocket the deck drops into
        translate([wall, wall, floor_t]) rounded_box(W - 2 * wall, D - 2 * wall, H, R - wall + 1);
        translate([rim, rim, ledge_z]) rounded_box(W - 2 * rim, D - 2 * rim, H, R - rim);
        // Cable exit at the back, right under the deck
        translate([u_x + (u_r - u_x) / 2 - exit_w / 2, D - wall - 1, ledge_z - exit_h])
            cube([exit_w, wall + 2, exit_h + 1]);
        // Pockets for 10 mm rubber feet
        for (x = [10, W - 10], y = [10, D - 10])
            translate([x, y, -0.01]) cylinder(d = 10.4, h = 0.8);
    }
    // Screw posts for the deck, merged into the corners
    for (p = post) translate([p[0], p[1], 0]) {
        difference() {
            hull() {
                cylinder(d = 7, h = ledge_z);
                translate([p[0] < W / 2 ? -4 : 4, p[1] < D / 2 ? -4 : 4, 0]) cylinder(d = 2, h = ledge_z);
            }
            translate([0, 0, floor_t]) cylinder(d = m3_pilot, h = ledge_z);
        }
    }
}

// --- deck -----------------------------------------------------------------------
// The U seen from above, grown inward by g: two cheeks and the back block
// around the bay the ToF sits in.
module u_2d(g) {
    difference() {
        translate([u_x + g, u_front + g]) square([u_r - u_x - 2 * g, u_back + u_depth - u_front - 2 * g]);
        translate([bay_l - g, u_front - 1]) square([bay_r - bay_l + 2 * g, u_back - u_front + 1 + g]);
    }
}

module u_body() {
    difference() {
        linear_extrude(u_top) u_2d(0);
        // Hollow, closed on top, open through the deck into the tray
        translate([0, 0, -1]) linear_extrude(u_top - u_wall + 1) u_2d(u_wall);
        // Cable holes from the bay into both cheeks, centred on the sockets
        for (x = [bay_l - u_wall - 1, bay_r - 1])
            translate([x, socket_y - cable_hole / 2, socket_z - cable_hole / 2])
                cube([u_wall + 2, cable_hole, cable_hole]);
        // Window behind the header row, for soldered pins
        translate([tof_x + TOF_HOLE + 2, u_back - 1, deck_t + tof_lift + TOF_HOLE - 1.5])
            cube([TOF_W - 2 * TOF_HOLE - 4, u_wall + 2, 3]);
    }
    // ToF standoffs point forward (toward -y)
    for (x = [TOF_HOLE, TOF_W - TOF_HOLE], z = [TOF_HOLE, TOF_H - TOF_HOLE])
        translate([tof_x + x, u_back, deck_t + tof_lift + z])
            rotate([90, 0, 0]) standoff(tof_gap, 5, m25_pilot);
}

module deck() {
    difference() {
        union() {
            translate([rim + fit, rim + fit, 0])
                rounded_box(W - 2 * (rim + fit), D - 2 * (rim + fit), deck_t, R - rim);
            translate([apds_x, apds_y, deck_t]) {
                for (p = APDS_HOLES) translate([p[0], p[1], 0]) standoff(apds_gap, 6, m3_pilot);
                for (p = APDS_SUPPORT) translate([p[0], p[1], 0]) cylinder(d = 5, h = apds_gap);
            }
        }
        // Into the U's hollow
        translate([0, 0, -1]) linear_extrude(deck_t + 2) u_2d(u_wall);
        translate([apds_x, apds_y, -1]) {
            // Long slot beside the socket: the cable leaves sideways, then bends down
            translate([-apds_slot, APDS_SOCKET_Y - 6, 0]) cube([apds_slot - 2, 12, deck_t + 2]);
            // Header pins (if soldered)
            translate([APDS_W / 2 - 5, -0.25, 0]) cube([10, 3.5, deck_t + 2]);
            translate([APDS_W / 2 - 6.5, 34.75, 0]) cube([13, 3.5, deck_t + 2]);
        }
        // Countersunk screws into the tray posts
        for (p = post) translate([p[0], p[1], -1]) {
            cylinder(d = m3_clear, h = deck_t + 2);
            translate([0, 0, deck_t + 1 - 1.7]) cylinder(d1 = m3_clear, d2 = 6.4, h = 1.71);
        }
    }
    u_body();
}

// --- output -----------------------------------------------------------------------
module boards() {   // the two breakouts where they sit, for previews
    translate([tof_x, tof_front, H + tof_lift]) cube([TOF_W, 1.6, TOF_H]);
    translate([apds_x, apds_y, H + apds_gap]) cube([APDS_W, APDS_L, 1.6]);
}

if (part == "tray") tray();
else if (part == "deck") deck();
else if (part == "boards") boards();
else {
    color("SteelBlue") tray();
    color("CornflowerBlue") translate([0, 0, ledge_z]) deck();
    // Ghost boards for checking the fit (F5 preview only)
    %translate([tof_x, tof_front, H + tof_lift]) cube([TOF_W, 1.6, TOF_H]);
    %translate([apds_x, apds_y, H + apds_gap]) cube([APDS_W, APDS_L, 1.6]);
}
