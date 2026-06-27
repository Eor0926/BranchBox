#!/usr/bin/env python3
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, Gdk, Gio, Pango, PangoCairo, GdkPixbuf, GLib
import cairo
import json
import math
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse, unquote

APP_NAME = "branchbox"
APP_TITLE = "BranchBox"

BASE_DATA_DIR = Path.home() / ".local" / "share" / APP_NAME
INSTANCES_DIR = BASE_DATA_DIR / "instances"
REGISTRY_FILE = BASE_DATA_DIR / "registry.json"
DEFAULT_INSTANCE_FILE = BASE_DATA_DIR / "default.branchbox"

DEFAULT_CONFIG = {
    "background_color": "rgb(216,216,216)",
    "background_opacity": 0.05,
    "background_shape": "morph",
    "fade_radius": 34,
    "halo_strength": 0.70,

    "label_backing_enabled": False,
    "label_backing_color": "rgb(216,216,216)",
    "label_backing_opacity": 0.95,
    "text_color": "rgb(255,255,255)",

    "line_color": "#000000",
    "line_width": 3,

    "font_size": 13,
    "icon_size": 42,
    "spacing_x": 165,
    "spacing_y": 105,
    "padding": 35,
    "label_width": 150,
}


def clamp(value, low, high):
    return max(low, min(high, value))


def safe_json_read(path):
    try:
        path = Path(path)
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text())
    except Exception:
        pass
    return {}


def safe_json_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def register_instance(instance_id, instance_file, name):
    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    registry = safe_json_read(REGISTRY_FILE)
    registry[instance_id] = {
        "file": str(Path(instance_file).expanduser().resolve()),
        "name": name,
    }
    safe_json_write(REGISTRY_FILE, registry)


def make_instance_file(path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = safe_json_read(path)
    changed = False

    if data.get("format") != 1:
        data["format"] = 1
        changed = True

    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        changed = True

    if not data.get("name"):
        data["name"] = path.stem if path.name else APP_TITLE
        changed = True

    config = DEFAULT_CONFIG.copy()
    config.update(data.get("config", {}))
    data["config"] = config

    if changed or not path.exists() or path.stat().st_size == 0:
        safe_json_write(path, data)

    return data


def get_instance_path_from_args():
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return Path(sys.argv[1]).expanduser().resolve()

    BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DEFAULT_INSTANCE_FILE


class TreeItem:
    def __init__(self, path, name, is_dir, depth=0):
        self.path = Path(path)
        self.name = name
        self.is_dir = is_dir
        self.depth = depth
        self.children = []
        self.x = 0
        self.y = 0
        self.item_rect = None
        self.label_rect = None
        self.label_h = 24


class DeskTree(Gtk.Window):
    def __init__(self, instance_file):
        self.instance_file = Path(instance_file).expanduser().resolve()
        self.instance_data = make_instance_file(self.instance_file)
        self.instance_id = self.instance_data["id"]
        self.instance_name = self.instance_data.get("name", self.instance_file.stem)
        register_instance(self.instance_id, self.instance_file, self.instance_name)

        self.config = DEFAULT_CONFIG.copy()
        self.config.update(self.instance_data.get("config", {}))

        self.data_dir = INSTANCES_DIR / self.instance_id / "items"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # New/empty BranchBox files open directly to their storage folder.
        if not any(self.data_dir.iterdir()):
            subprocess.Popen(["nemo", str(self.data_dir)])
            raise SystemExit(0)

        super().__init__(title=self.instance_name)

        self.set_decorated(False)
        self.set_resizable(False)

        screen = self.get_screen()
        visual = screen.get_rgba_visual()
        if visual and screen.is_composited():
            self.set_visual(visual)
        self.set_app_paintable(True)
        self.set_accept_focus(True)
        self.set_focus_on_map(True)

        self.close_on_focus_lost = False
        self.suppress_focus_close = False
        self.dialog_open = False
        self.connect("focus-out-event", self.on_focus_out)
        GLib.timeout_add(350, self.enable_focus_close)

        self.items_hitboxes = []
        self.hovered_node = None
        self.icon_cache = {}
        self.all_nodes = []
        self.visible_nodes = []

        self.area = Gtk.DrawingArea()
        self.area.set_can_focus(True)
        self.area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )

        self.area.connect("draw", self.on_draw)
        self.area.connect("button-press-event", self.on_button_press)
        self.area.connect("motion-notify-event", self.on_mouse_motion)
        self.area.connect("leave-notify-event", self.on_mouse_leave)

        self.add(self.area)
        self.rebuild()

    def enable_focus_close(self):
        self.close_on_focus_lost = True
        return False

    def on_focus_out(self, widget, event):
        if self.close_on_focus_lost and not self.suppress_focus_close and not self.dialog_open:
            GLib.idle_add(self.destroy)
        return False

    def save_instance(self):
        self.instance_data["format"] = 1
        self.instance_data["id"] = self.instance_id
        self.instance_data["name"] = self.instance_name
        self.instance_data["config"] = self.config
        safe_json_write(self.instance_file, self.instance_data)
        register_instance(self.instance_id, self.instance_file, self.instance_name)

    def rebuild(self):
        self.instance_data = make_instance_file(self.instance_file)
        self.config = DEFAULT_CONFIG.copy()
        self.config.update(self.instance_data.get("config", {}))
        self.root = self.scan_folder(self.data_dir, self.instance_name, 0)
        self.layout_tree()
        self.area.queue_draw()

    def scan_folder(self, path, label, depth):
        node = TreeItem(path, label, True, depth)

        try:
            children = sorted(Path(path).iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            children = []

        for child in children:
            if child.name.startswith("."):
                continue

            if child.is_dir():
                sub = self.scan_folder(child, child.name, depth + 1)
                if sub.children:
                    node.children.append(sub)
            else:
                node.children.append(TreeItem(child, child.name, False, depth + 1))

        return node

    def collect_nodes(self, node):
        nodes = [node]
        for child in node.children:
            nodes.extend(self.collect_nodes(child))
        return nodes

    def measure_label(self, text):
        font_size = int(self.config.get("font_size", 13))
        label_width = int(self.config.get("label_width", 150))

        layout = self.create_pango_layout(text)
        layout.set_font_description(Pango.FontDescription(f"Sans {font_size}"))
        layout.set_width(label_width * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_alignment(Pango.Alignment.CENTER)

        _, h = layout.get_pixel_size()
        return max(24, h + 10)

    def layout_tree(self):
        spacing_x = int(self.config.get("spacing_x", 165))
        spacing_y = int(self.config.get("spacing_y", 105))
        padding = int(self.config.get("padding", 35))
        icon_size = int(self.config.get("icon_size", 42))
        label_width = int(self.config.get("label_width", 150))
        fade_radius = int(self.config.get("fade_radius", 34))

        leaf_index = 0

        def layout_node(node, depth):
            nonlocal leaf_index

            node.depth = depth
            node.y = padding + depth * spacing_y

            if not node.children:
                node.x = padding + leaf_index * spacing_x
                leaf_index += 1
                return node.x

            child_positions = [layout_node(child, depth + 1) for child in node.children]
            node.x = sum(child_positions) / len(child_positions)
            return node.x

        layout_node(self.root, 0)

        self.all_nodes = self.collect_nodes(self.root)
        self.visible_nodes = [n for n in self.all_nodes if not n.is_dir]

        if not self.visible_nodes:
            subprocess.Popen(["nemo", str(self.data_dir)])
            raise SystemExit(0)

        min_x = 999999
        min_y = 999999
        max_x = -999999
        max_y = -999999

        for node in self.visible_nodes:
            node.label_h = self.measure_label(node.name)

            item_w = max(icon_size, label_width) + 18
            item_h = icon_size + node.label_h + 22

            x1 = node.x - item_w / 2
            y1 = node.y - icon_size / 2 - 8
            x2 = node.x + item_w / 2
            y2 = y1 + item_h

            node.item_rect = (x1, y1, x2, y2)

            min_x = min(min_x, x1)
            min_y = min(min_y, y1)
            max_x = max(max_x, x2)
            max_y = max(max_y, y2)

        for node in self.all_nodes:
            min_x = min(min_x, node.x - 12)
            min_y = min(min_y, node.y - 12)
            max_x = max(max_x, node.x + 12)
            max_y = max(max_y, node.y + 12)

        min_x -= fade_radius
        min_y -= fade_radius
        max_x += fade_radius
        max_y += fade_radius

        shift_x = padding - min_x
        shift_y = padding - min_y

        for node in self.all_nodes:
            node.x += shift_x
            node.y += shift_y

        width = int((max_x - min_x) + padding * 2)
        height = int((max_y - min_y) + padding * 2)

        width = max(260, width)
        height = max(140, height)

        self.set_default_size(width, height)
        self.resize(width, height)
        self.area.set_size_request(width, height)

    def position_near_pointer(self):
        display = Gdk.Display.get_default()
        if not display:
            return

        try:
            seat = display.get_default_seat()
            pointer = seat.get_pointer()
            _, px, py = pointer.get_position()
        except Exception:
            try:
                manager = display.get_device_manager()
                pointer = manager.get_client_pointer()
                _, px, py = pointer.get_position()
            except Exception:
                return

        width, height = self.get_size()

        root_x = getattr(self.root, "x", 20)
        root_y = getattr(self.root, "y", 20)

        target_x = px - root_x
        target_y = py - root_y

        try:
            monitor = display.get_monitor_at_point(px, py)
            workarea = monitor.get_workarea()

            min_x = workarea.x
            min_y = workarea.y
            max_x = workarea.x + workarea.width - width
            max_y = workarea.y + workarea.height - height

            x = clamp(target_x, min_x, max_x)
            y = clamp(target_y, min_y, max_y)
        except Exception:
            x = max(0, target_x)
            y = max(0, target_y)

        self.move(int(x), int(y))

    def refresh(self):
        self.hovered_node = None
        self.icon_cache.clear()
        self.rebuild()

    def rgba_from_config(self, key, fallback="#000000", alpha=None):
        color = Gdk.RGBA()
        if not color.parse(str(self.config.get(key, fallback))):
            color.parse(fallback)
        if alpha is not None:
            color.alpha = alpha
        return color

    def on_draw(self, widget, cr):
        self.items_hitboxes = []

        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)

        if self.config.get("background_shape", "morph") == "rectangle":
            self.draw_rectangle_background(cr)
        else:
            self.draw_morphed_background(cr)

        self.draw_connections(cr, self.root)

        for node in self.visible_nodes:
            self.draw_file_item(cr, node)

    def draw_rectangle_background(self, cr):
        bg = self.rgba_from_config("background_color", "#d8d8d8")
        opacity = clamp(float(self.config.get("background_opacity", 0.85)), 0.0, 1.0)
        cr.set_source_rgba(bg.red, bg.green, bg.blue, opacity)
        cr.paint()

    def draw_morphed_background(self, cr):
        bg = self.rgba_from_config("background_color", "#d8d8d8")
        opacity = clamp(float(self.config.get("background_opacity", 0.85)), 0.0, 1.0)
        strength = clamp(float(self.config.get("halo_strength", 0.70)), 0.0, 1.0)
        fade_radius = max(4, int(self.config.get("fade_radius", 34)))
        icon_size = int(self.config.get("icon_size", 42))
        line_width = float(self.config.get("line_width", 3))
        label_width = int(self.config.get("label_width", 150))
        draw_label_halo = bool(self.config.get("label_backing_enabled", True))

        layers = 9

        # Draw a distance-fade style halo around the tree lines and each element.
        # Icons and labels are handled as separate shapes so the old large
        # square behind each icon is reduced.
        for i in range(layers, 0, -1):
            t = i / layers
            alpha = opacity * strength * (1 - t) ** 1.65
            extra = fade_radius * t

            cr.set_source_rgba(bg.red, bg.green, bg.blue, alpha)
            self.draw_connection_halo(cr, self.root, line_width + extra * 2)

            for node in self.visible_nodes:
                # Small icon halo.
                icon_w = icon_size + 18 + extra * 2
                icon_h = icon_size + 18 + extra * 2
                icon_x = node.x - icon_w / 2
                icon_y = node.y - icon_size / 2 - 9 - extra
                self.draw_rounded_rect(cr, icon_x, icon_y, icon_w, icon_h, 12 + extra)
                cr.fill()

                # Optional separate label halo. This is only drawn when text backing
                # is enabled, so transparent-label setups stay clean.
                if draw_label_halo:
                    label_h = self.measure_label(node.name)
                    label_x = node.x - label_width / 2 + 3 - extra
                    label_y = node.y + icon_size / 2 + 7 - extra
                    self.draw_rounded_rect(
                        cr,
                        label_x,
                        label_y,
                        label_width - 6 + extra * 2,
                        label_h + extra * 2,
                        6 + extra,
                    )
                    cr.fill()

        cr.set_source_rgba(bg.red, bg.green, bg.blue, opacity)
        self.draw_connection_halo(cr, self.root, line_width + 4)

        for node in self.visible_nodes:
            # Solid core behind the icon only.
            icon_w = icon_size + 18
            icon_h = icon_size + 18
            icon_x = node.x - icon_w / 2
            icon_y = node.y - icon_size / 2 - 9
            self.draw_rounded_rect(cr, icon_x, icon_y, icon_w, icon_h, 12)
            cr.fill()

            if draw_label_halo:
                label_h = self.measure_label(node.name)
                label_x = node.x - label_width / 2 + 3
                label_y = node.y + icon_size / 2 + 7
                self.draw_rounded_rect(cr, label_x, label_y, label_width - 6, label_h, 6)
                cr.fill()

    def draw_connection_halo(self, cr, node, width):
        icon_size = int(self.config.get("icon_size", 42))
        old_width = cr.get_line_width()
        cr.set_line_width(width)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        for child in node.children:
            start_x = node.x
            start_y = node.y

            if child.is_dir:
                end_x = child.x
                end_y = child.y
            else:
                end_x = child.x
                end_y = child.y - icon_size / 2 - 10

            cr.move_to(start_x, start_y)
            cr.line_to(end_x, end_y)
            cr.stroke()
            self.draw_connection_halo(cr, child, width)

        cr.set_line_width(old_width)

    def draw_connections(self, cr, node):
        line_color = self.rgba_from_config("line_color", "#000000")
        cr.set_source_rgba(line_color.red, line_color.green, line_color.blue, line_color.alpha)
        cr.set_line_width(float(self.config.get("line_width", 3)))
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)

        icon_size = int(self.config.get("icon_size", 42))

        for child in node.children:
            start_x = node.x
            start_y = node.y

            if child.is_dir:
                end_x = child.x
                end_y = child.y
            else:
                end_x = child.x
                end_y = child.y - icon_size / 2 - 10

            cr.move_to(start_x, start_y)
            cr.line_to(end_x, end_y)
            cr.stroke()

            self.draw_connections(cr, child)

    def draw_rounded_rect(self, cr, x, y, w, h, r):
        r = min(r, w / 2, h / 2)
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def draw_file_item(self, cr, node):
        font_size = int(self.config.get("font_size", 13))
        icon_size = int(self.config.get("icon_size", 42))
        label_width = int(self.config.get("label_width", 150))

        label_h = self.measure_label(node.name)

        icon_x = int(node.x - icon_size / 2)
        icon_y = int(node.y - icon_size / 2)

        label_x = int(node.x - label_width / 2)
        label_y = int(node.y + icon_size / 2 + 7)

        item_x = int(node.x - max(icon_size, label_width) / 2 - 9)
        item_y = int(icon_y - 8)
        item_w = int(max(icon_size, label_width) + 18)
        item_h = int(icon_size + label_h + 22)

        if node == self.hovered_node:
            cr.set_source_rgba(0.25, 0.45, 0.95, 0.20)
            self.draw_rounded_rect(cr, item_x, item_y, item_w, item_h, 10)
            cr.fill()

        pixbuf = self.get_icon_pixbuf(node, icon_size)

        if pixbuf:
            px = icon_x + (icon_size - pixbuf.get_width()) / 2
            py = icon_y + (icon_size - pixbuf.get_height()) / 2
            Gdk.cairo_set_source_pixbuf(cr, pixbuf, px, py)
            cr.paint()
        else:
            cr.set_source_rgb(0.95, 0.95, 0.95)
            cr.rectangle(icon_x, icon_y, icon_size * 0.75, icon_size)
            cr.fill_preserve()
            cr.set_source_rgb(0.1, 0.1, 0.1)
            cr.stroke()

        if bool(self.config.get("label_backing_enabled", True)):
            backing = self.rgba_from_config("label_backing_color", "#d8d8d8")
            backing_opacity = clamp(float(self.config.get("label_backing_opacity", 0.95)), 0.0, 1.0)
            cr.set_source_rgba(backing.red, backing.green, backing.blue, backing_opacity)
            self.draw_rounded_rect(cr, label_x + 3, label_y, label_width - 6, label_h, 6)
            cr.fill()

        if node == self.hovered_node:
            cr.set_source_rgba(0.25, 0.45, 0.95, 0.13)
            self.draw_rounded_rect(cr, label_x + 3, label_y, label_width - 6, label_h, 6)
            cr.fill()

        layout = PangoCairo.create_layout(cr)
        layout.set_text(node.name, -1)
        layout.set_font_description(Pango.FontDescription(f"Sans {font_size}"))
        layout.set_width(label_width * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)
        layout.set_alignment(Pango.Alignment.CENTER)

        text_color = self.rgba_from_config("text_color", "#000000")
        cr.set_source_rgba(text_color.red, text_color.green, text_color.blue, text_color.alpha)
        cr.move_to(label_x, label_y + 5)
        PangoCairo.show_layout(cr, layout)

        self.items_hitboxes.append(
            {
                "node": node,
                "x1": item_x,
                "y1": item_y,
                "x2": item_x + item_w,
                "y2": item_y + item_h,
            }
        )

    def icon_from_value(self, value, size):
        if not value:
            return None

        value = str(value).strip().strip('"')
        if not value:
            return None

        if "file://" in value and not value.startswith("file://"):
            start = value.find("file://")
            value = value[start:].split()[0].strip("'\"[](),")

        if value.startswith("file://"):
            parsed = urlparse(value)
            value = unquote(parsed.path)

        if value.startswith("~"):
            value = str(Path(value).expanduser())

        if value.startswith("/"):
            try:
                return GdkPixbuf.Pixbuf.new_from_file_at_scale(value, size, size, True)
            except Exception:
                return None

        theme = Gtk.IconTheme.get_default()
        names = [value]

        if value.endswith((".png", ".svg", ".xpm")):
            names.append(Path(value).stem)

        for name in names:
            try:
                return theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
            except Exception:
                pass

        return None

    def get_desktop_icon_value(self, path):
        if Path(path).suffix.lower() != ".desktop":
            return None

        try:
            for line in Path(path).read_text(errors="ignore").splitlines():
                line = line.strip()
                if line.startswith("Icon="):
                    return line.split("=", 1)[1].strip()
        except Exception:
            return None

        return None

    def get_metadata_icon_values(self, path):
        values = []

        try:
            info = Gio.File.new_for_path(str(path)).query_info(
                "metadata::custom-icon,metadata::custom-icon-name,standard::icon,standard::symbolic-icon,standard::content-type",
                Gio.FileQueryInfoFlags.NONE,
                None,
            )

            for attr in ["metadata::custom-icon", "metadata::custom-icon-name"]:
                try:
                    value = info.get_attribute_as_string(attr)
                    if value:
                        values.append(value)
                except Exception:
                    pass
        except Exception:
            pass

        return values

    def get_icon_pixbuf(self, node, size):
        try:
            mtime = node.path.stat().st_mtime_ns
        except Exception:
            mtime = 0

        cache_key = f"{node.path}:{mtime}:{size}"

        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]

        candidates = []
        candidates.extend(self.get_metadata_icon_values(node.path))

        desktop_icon = self.get_desktop_icon_value(node.path)
        if desktop_icon:
            candidates.append(desktop_icon)

        for value in candidates:
            pixbuf = self.icon_from_value(value, size)
            if pixbuf:
                self.icon_cache[cache_key] = pixbuf
                return pixbuf

        try:
            info = Gio.File.new_for_path(str(node.path)).query_info(
                "standard::icon,standard::content-type",
                Gio.FileQueryInfoFlags.NONE,
                None,
            )
            gicon = info.get_icon()
        except Exception:
            if str(node.path).lower().endswith(".exe"):
                gicon = Gio.ThemedIcon.new("application-x-executable")
            else:
                gicon = Gio.ThemedIcon.new("text-x-generic")

        theme = Gtk.IconTheme.get_default()

        try:
            icon_info = theme.lookup_by_gicon(gicon, size, Gtk.IconLookupFlags.FORCE_SIZE)
            if icon_info:
                pixbuf = icon_info.load_icon()
                self.icon_cache[cache_key] = pixbuf
                return pixbuf
        except Exception:
            pass

        fallback_names = [
            "application-x-ms-dos-executable" if str(node.path).lower().endswith(".exe") else "text-x-generic",
            "application-x-executable",
            "application-x-generic",
        ]

        for name in fallback_names:
            try:
                pixbuf = theme.load_icon(name, size, Gtk.IconLookupFlags.FORCE_SIZE)
                self.icon_cache[cache_key] = pixbuf
                return pixbuf
            except Exception:
                continue

        self.icon_cache[cache_key] = None
        return None

    def hit_test(self, x, y):
        for box in reversed(self.items_hitboxes):
            if box["x1"] <= x <= box["x2"] and box["y1"] <= y <= box["y2"]:
                return box["node"]
        return None

    def on_mouse_motion(self, widget, event):
        node = self.hit_test(event.x, event.y)

        if node != self.hovered_node:
            self.hovered_node = node
            self.area.queue_draw()

        return False

    def on_mouse_leave(self, widget, event):
        if self.hovered_node is not None:
            self.hovered_node = None
            self.area.queue_draw()

        return False

    def on_button_press(self, widget, event):
        clicked = self.hit_test(event.x, event.y)

        if event.button == 1 and event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            if clicked:
                self.open_item(clicked, close_after=True)
                return True

        elif event.button == 1 and not clicked:
            self.begin_move_drag(event.button, int(event.x_root), int(event.y_root), event.time)
            return True

        elif event.button == 3:
            if clicked:
                self.show_item_menu(event, clicked)
            else:
                self.show_background_menu(event)
            return True

        return False

    def open_item(self, node, close_after=False):
        path = str(node.path)

        try:
            if path.lower().endswith(".exe"):
                subprocess.Popen(["wine", path])
            else:
                subprocess.Popen(["xdg-open", path])
        finally:
            if close_after:
                self.destroy()

    def open_storage_folder(self):
        subprocess.Popen(["nemo", str(self.data_dir)])
        self.destroy()

    def show_item_menu(self, event, node):
        self.suppress_focus_close = True
        menu = Gtk.Menu()

        open_item = Gtk.MenuItem(label="Open")
        open_item.connect("activate", lambda *_: self.open_item(node, close_after=True))
        menu.append(open_item)

        open_folder = Gtk.MenuItem(label="Open Containing Folder")
        open_folder.connect("activate", lambda *_: subprocess.Popen(["nemo", str(node.path.parent)]))
        menu.append(open_folder)

        refresh = Gtk.MenuItem(label="Refresh")
        refresh.connect("activate", lambda *_: self.refresh())
        menu.append(refresh)

        menu.connect("deactivate", lambda *_: setattr(self, "suppress_focus_close", False))
        menu.show_all()
        menu.popup_at_pointer(event)

    def show_background_menu(self, event):
        self.suppress_focus_close = True
        menu = Gtk.Menu()

        open_folder = Gtk.MenuItem(label="Open Storage Folder")
        open_folder.connect("activate", lambda *_: self.open_storage_folder())
        menu.append(open_folder)

        edit_appearance = Gtk.MenuItem(label="Edit Appearance")
        edit_appearance.connect("activate", lambda *_: self.edit_appearance())
        menu.append(edit_appearance)

        refresh = Gtk.MenuItem(label="Refresh")
        refresh.connect("activate", lambda *_: self.refresh())
        menu.append(refresh)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda *_: Gtk.main_quit())
        menu.append(quit_item)

        menu.connect("deactivate", lambda *_: setattr(self, "suppress_focus_close", False))
        menu.show_all()
        menu.popup_at_pointer(event)

    def edit_appearance(self):
        self.suppress_focus_close = True
        self.dialog_open = True

        dialog = Gtk.Dialog(
            title="Edit Appearance",
            parent=self,
            flags=0,
            buttons=("Cancel", Gtk.ResponseType.CANCEL, "Save", Gtk.ResponseType.OK),
        )

        dialog.set_default_size(430, 560)

        box = dialog.get_content_area()
        box.set_spacing(10)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(14)
        box.set_margin_end(14)

        def section_title(text):
            label = Gtk.Label()
            label.set_markup(f"<b><big>{text}</big></b>")
            label.set_xalign(0)
            return label

        def color_row(label_text, rgba):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)
            row.pack_start(label, True, True, 0)

            button = Gtk.ColorButton()
            button.set_rgba(rgba)
            row.pack_start(button, False, False, 0)
            return row, button

        def slider(label_text, low, high, value):
            label = Gtk.Label(label=label_text)
            label.set_xalign(0)

            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, low, high, 1)
            scale.set_value(value)
            scale.set_digits(0)
            scale.set_hexpand(True)

            box.pack_start(label, False, False, 0)
            box.pack_start(scale, False, False, 0)

            return scale

        box.pack_start(section_title("Background Appearance"), False, False, 0)

        background_color_row, background_color_button = color_row(
            "Background Color", self.rgba_from_config("background_color", "#d8d8d8")
        )
        box.pack_start(background_color_row, False, False, 0)

        morph_check = Gtk.CheckButton(label="Morphed background around icons and lines")
        morph_check.set_active(self.config.get("background_shape", "morph") == "morph")
        box.pack_start(morph_check, False, False, 0)

        opacity = slider("Background Opacity", 0, 100, float(self.config.get("background_opacity", 0.85)) * 100)
        fade = slider("Fade Distance", 4, 100, float(self.config.get("fade_radius", 34)))
        strength = slider("Fade Strength", 0, 100, float(self.config.get("halo_strength", 0.70)) * 100)

        box.pack_start(Gtk.Label(label=""), False, False, 8)
        box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 6)
        box.pack_start(Gtk.Label(label=""), False, False, 8)

        box.pack_start(section_title("Text Appearance"), False, False, 0)

        text_color_row, text_color_button = color_row("Text Color", self.rgba_from_config("text_color", "#000000"))
        box.pack_start(text_color_row, False, False, 0)

        backing_enabled = Gtk.CheckButton(label="Show backing behind file names")
        backing_enabled.set_active(bool(self.config.get("label_backing_enabled", True)))
        box.pack_start(backing_enabled, False, False, 0)

        backing_color_row, backing_color_button = color_row(
            "Text Backing Color", self.rgba_from_config("label_backing_color", "#d8d8d8")
        )
        box.pack_start(backing_color_row, False, False, 0)

        backing_opacity = slider(
            "Text Backing Opacity", 0, 100, float(self.config.get("label_backing_opacity", 0.95)) * 100
        )

        dialog.show_all()
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.config["background_color"] = background_color_button.get_rgba().to_string()
            self.config["background_opacity"] = opacity.get_value() / 100
            self.config["background_shape"] = "morph" if morph_check.get_active() else "rectangle"
            self.config["fade_radius"] = int(fade.get_value())
            self.config["halo_strength"] = strength.get_value() / 100

            self.config["text_color"] = text_color_button.get_rgba().to_string()
            self.config["label_backing_enabled"] = backing_enabled.get_active()
            self.config["label_backing_color"] = backing_color_button.get_rgba().to_string()
            self.config["label_backing_opacity"] = backing_opacity.get_value() / 100

            self.save_instance()
            self.refresh()

        dialog.destroy()
        self.dialog_open = False
        self.suppress_focus_close = False


def main():
    instance_file = get_instance_path_from_args()

    win = DeskTree(instance_file)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    win.position_near_pointer()
    Gtk.main()


if __name__ == "__main__":
    main()
