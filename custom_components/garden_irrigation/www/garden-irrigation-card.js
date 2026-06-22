/*
 * Garden Irrigation card
 * A custom Lovelace card that sets up zones and schedules for the
 * `garden_irrigation` integration. Plain custom element (no build step).
 */

const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

const STYLES = `
  :host { display: block; }
  ha-card { padding: 16px 18px 18px; }
  .header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
  }
  .header ha-icon { color: var(--primary-color); --mdc-icon-size: 26px; }
  .header h1 {
    font-size: 1.5rem; font-weight: 700; margin: 0; flex: 1;
    color: var(--primary-text-color);
  }
  button {
    font: inherit; cursor: pointer; border-radius: 10px;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    padding: 8px 14px; display: inline-flex; align-items: center; gap: 6px;
    transition: background .15s, border-color .15s;
  }
  button:hover { background: var(--secondary-background-color); }
  button.primary { font-weight: 600; }
  button.add-zone { font-weight: 600; }
  button:disabled { opacity: .5; cursor: default; }
  .zone {
    border: 1px solid var(--divider-color); border-radius: 16px;
    padding: 16px 18px; margin-top: 14px;
  }
  .zone.running {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 1px var(--primary-color);
  }
  .zone-head { display: flex; align-items: flex-start; gap: 10px; }
  .zone-head .titles { flex: 1; min-width: 0; }
  .zone-name {
    font-size: 1.15rem; font-weight: 700; color: var(--primary-text-color);
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  }
  .zone-sub {
    font-family: var(--code-font-family, monospace);
    color: var(--secondary-text-color); font-size: .9rem; margin-top: 2px;
  }
  .badge {
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--primary-color); color: var(--text-primary-color, #fff);
    border-radius: 999px; padding: 3px 10px; font-size: .8rem; font-weight: 600;
    opacity: .92;
  }
  .badge ha-icon { --mdc-icon-size: 15px; }
  .icon-btn {
    border-radius: 10px; padding: 8px; line-height: 0;
  }
  .icon-btn ha-icon { --mdc-icon-size: 20px; color: var(--secondary-text-color); }
  .row { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
  .row .label { width: 86px; color: var(--primary-text-color); font-weight: 500; }
  input[type="range"] { flex: 1; accent-color: var(--primary-color); height: 4px; }
  .dur-value { font-weight: 700; min-width: 56px; text-align: right; }
  .sched-label { color: var(--primary-text-color); font-weight: 500; margin-top: 14px; }
  .chips { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 8px; }
  .chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--secondary-background-color); border-radius: 999px;
    padding: 5px 10px; font-size: .92rem;
  }
  .chip ha-icon { --mdc-icon-size: 16px; color: var(--secondary-text-color); }
  .chip .x { cursor: pointer; color: var(--secondary-text-color); padding: 0 2px; }
  .chip .x:hover { color: var(--error-color); }
  .no-sched { color: var(--secondary-text-color); }
  .time-add {
    display: inline-flex; align-items: center; gap: 6px;
    border: 1px solid var(--divider-color); border-radius: 10px; padding: 4px 8px;
  }
  .time-add input[type="time"] {
    border: none; background: transparent; color: var(--primary-text-color);
    font: inherit;
  }
  hr { border: none; border-top: 1px solid var(--divider-color); margin: 16px 0; }
  .actions { display: flex; align-items: center; gap: 14px; }
  .status { color: var(--secondary-text-color); }
  .status b { color: var(--primary-text-color); font-variant-numeric: tabular-nums; }
  button.stop { color: var(--error-color); border-color: var(--error-color); }
  .form {
    border: 1px dashed var(--divider-color); border-radius: 14px;
    padding: 14px 16px; margin-top: 12px;
    display: grid; gap: 10px;
  }
  .form .field { display: flex; flex-direction: column; gap: 4px; }
  .form label { font-size: .85rem; color: var(--secondary-text-color); }
  .form input[type="text"], .form input[type="number"] {
    font: inherit; padding: 8px 10px; border-radius: 8px;
    border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
  }
  .form .form-actions { display: flex; gap: 10px; justify-content: flex-end; }
  .empty { color: var(--secondary-text-color); margin-top: 12px; }
`;

class GardenIrrigationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._zones = [];
    this._configured = true;
    this._fetched = false;
    this._addOpen = false;
    this._sig = null;
    this._refs = {};
    this._tick = this._tick.bind(this);
  }

  setConfig(config) {
    this._config = config || {};
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._fetched) {
      this._fetched = true;
      this._fetchZones();
    }
    this._sync();
  }

  getCardSize() {
    return 2 + this._zones.length * 4;
  }

  static getStubConfig() {
    return { title: "Garden watering" };
  }

  connectedCallback() {
    this._timer = setInterval(this._tick, 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
    clearTimeout(this._retry);
  }

  /* ---------- data ---------- */

  async _ws(message) {
    return this._hass.connection.sendMessagePromise(message);
  }

  async _fetchZones() {
    try {
      const res = await this._ws({ type: "garden_irrigation/get" });
      this._configured = res.configured;
      this._zones = res.zones || [];
      this._mode = res.mode;
    } catch (err) {
      this._configured = false;
      this._error = err && err.message ? err.message : String(err);
    }
    this._sig = null; // force rebuild
    this._sync();

    // A freshly added zone's entity is created during the async reload, so its
    // entity_id can be momentarily null — refetch shortly until it resolves.
    clearTimeout(this._retry);
    if (this._configured && this._zones.some((z) => !z.entity_id)) {
      this._retry = setTimeout(() => this._fetchZones(), 1000);
    }
  }

  /* ---------- render orchestration ---------- */

  _computeSig() {
    return JSON.stringify({
      configured: this._configured,
      addOpen: this._addOpen,
      zones: this._zones,
    });
  }

  _sync() {
    if (!this._hass) return;
    const sig = this._computeSig();
    if (sig !== this._sig) {
      this._sig = sig;
      this._build();
    }
    this._update();
  }

  _stateFor(zone) {
    if (!zone.entity_id) return null;
    return this._hass.states[zone.entity_id] || null;
  }

  /* ---------- build (structure) ---------- */

  _build() {
    this._refs = {};
    const root = document.createElement("div");
    const style = document.createElement("style");
    style.textContent = STYLES;

    const card = document.createElement("ha-card");

    // Header
    const header = document.createElement("div");
    header.className = "header";
    header.innerHTML = `
      <ha-icon icon="mdi:water"></ha-icon>
      <h1>${this._escape(this._config.title || "Garden watering")}</h1>
    `;
    const addBtn = document.createElement("button");
    addBtn.className = "add-zone";
    addBtn.innerHTML = `<ha-icon icon="mdi:plus"></ha-icon> Add zone`;
    addBtn.addEventListener("click", () => {
      this._addOpen = !this._addOpen;
      this._sig = null;
      this._sync();
    });
    header.appendChild(addBtn);
    card.appendChild(header);

    if (!this._configured) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent =
        "Garden Irrigation is not set up yet. Add the integration under Settings → Devices & Services.";
      card.appendChild(empty);
      root.appendChild(style);
      root.appendChild(card);
      this.shadowRoot.replaceChildren(root);
      return;
    }

    if (this._addOpen) {
      card.appendChild(this._buildAddForm());
    }

    if (this._zones.length === 0 && !this._addOpen) {
      const empty = document.createElement("div");
      empty.className = "empty";
      empty.textContent = "No zones yet. Use “Add zone” to create one.";
      card.appendChild(empty);
    }

    for (const zone of this._zones) {
      card.appendChild(this._buildZone(zone));
    }

    root.appendChild(style);
    root.appendChild(card);
    this.shadowRoot.replaceChildren(root);
  }

  _buildAddForm() {
    const form = document.createElement("div");
    form.className = "form";
    form.innerHTML = `
      <div class="field">
        <label>Zone name</label>
        <input type="text" id="gi-name" placeholder="e.g. Front lawn" />
      </div>
      <div class="field">
        <label>Switch / relay</label>
        <div id="gi-picker"></div>
      </div>
      <div class="field">
        <label>Duration (minutes)</label>
        <input type="number" id="gi-dur" min="1" max="60" value="10" />
      </div>
      <div class="form-actions">
        <button id="gi-cancel">Cancel</button>
        <button id="gi-save" class="primary">Save zone</button>
      </div>
    `;

    // Entity picker (native HA element when available, else a text input).
    const pickerHost = form.querySelector("#gi-picker");
    let getEntity;
    if (customElements.get("ha-entity-picker")) {
      const picker = document.createElement("ha-entity-picker");
      picker.hass = this._hass;
      picker.includeDomains = ["switch", "input_boolean"];
      picker.allowCustomEntity = false;
      pickerHost.appendChild(picker);
      getEntity = () => picker.value;
    } else {
      const inp = document.createElement("input");
      inp.type = "text";
      inp.placeholder = "switch.valve_front_lawn";
      pickerHost.appendChild(inp);
      getEntity = () => inp.value.trim();
    }

    form.querySelector("#gi-cancel").addEventListener("click", () => {
      this._addOpen = false;
      this._sig = null;
      this._sync();
    });

    form.querySelector("#gi-save").addEventListener("click", async () => {
      const name = form.querySelector("#gi-name").value.trim();
      const switch_entity = getEntity();
      const duration = parseInt(form.querySelector("#gi-dur").value, 10) || 10;
      if (!name || !switch_entity) {
        this._toast("Enter a name and pick a switch.");
        return;
      }
      try {
        await this._ws({
          type: "garden_irrigation/zone/add",
          name,
          switch_entity,
          duration,
        });
        this._addOpen = false;
        await this._fetchZones();
      } catch (err) {
        this._toast(`Could not add zone: ${err.message || err}`);
      }
    });

    return form;
  }

  _buildZone(zone) {
    const refs = {};
    const el = document.createElement("div");
    el.className = "zone";
    refs.el = el;

    // Head
    const head = document.createElement("div");
    head.className = "zone-head";
    head.innerHTML = `
      <div class="titles">
        <div class="zone-name">
          <span>${this._escape(zone.name)}</span>
          <span class="badge" hidden>
            <ha-icon icon="mdi:water"></ha-icon><span class="badge-text"></span>
          </span>
        </div>
        <div class="zone-sub">${this._escape(zone.switch_entity || "")}</div>
      </div>
    `;
    const del = document.createElement("button");
    del.className = "icon-btn";
    del.innerHTML = `<ha-icon icon="mdi:trash-can-outline"></ha-icon>`;
    del.addEventListener("click", () => this._deleteZone(zone));
    head.appendChild(del);
    el.appendChild(head);
    refs.badge = head.querySelector(".badge");
    refs.badgeText = head.querySelector(".badge-text");

    // Duration
    const durRow = document.createElement("div");
    durRow.className = "row";
    durRow.innerHTML = `<span class="label">Duration</span>`;
    const slider = document.createElement("input");
    slider.type = "range";
    slider.min = "1";
    slider.max = "60";
    slider.step = "1";
    slider.value = String(zone.duration);
    const durVal = document.createElement("span");
    durVal.className = "dur-value";
    durVal.textContent = `${zone.duration} min`;
    slider.addEventListener("input", () => {
      durVal.textContent = `${slider.value} min`;
    });
    slider.addEventListener("change", () =>
      this._updateZone(zone, { duration: parseInt(slider.value, 10) })
    );
    durRow.appendChild(slider);
    durRow.appendChild(durVal);
    el.appendChild(durRow);
    refs.slider = slider;
    refs.durVal = durVal;

    // Schedules
    const schedLabel = document.createElement("div");
    schedLabel.className = "sched-label";
    schedLabel.textContent = "Schedules";
    el.appendChild(schedLabel);

    const chips = document.createElement("div");
    chips.className = "chips";
    const schedules = zone.schedules || [];
    if (schedules.length === 0) {
      const none = document.createElement("span");
      none.className = "no-sched";
      none.textContent = "No schedules";
      chips.appendChild(none);
    }
    schedules.forEach((s, index) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `<ha-icon icon="mdi:clock-outline"></ha-icon><span>${this._escape(
        s.time
      )}</span><span class="x" title="Remove">✕</span>`;
      chip
        .querySelector(".x")
        .addEventListener("click", () => this._removeSchedule(zone, index));
      chips.appendChild(chip);
    });

    // Time picker + Add
    const timeAdd = document.createElement("span");
    timeAdd.className = "time-add";
    const timeInput = document.createElement("input");
    timeInput.type = "time";
    timeAdd.appendChild(timeInput);
    const clock = document.createElement("ha-icon");
    clock.setAttribute("icon", "mdi:clock-outline");
    clock.style.setProperty("--mdc-icon-size", "18px");
    clock.style.color = "var(--secondary-text-color)";
    timeAdd.appendChild(clock);
    chips.appendChild(timeAdd);

    const addSched = document.createElement("button");
    addSched.textContent = "Add";
    addSched.addEventListener("click", () => {
      if (!timeInput.value) {
        this._toast("Pick a time first.");
        return;
      }
      this._addSchedule(zone, timeInput.value);
    });
    chips.appendChild(addSched);
    el.appendChild(chips);

    el.appendChild(document.createElement("hr"));

    // Actions
    const actions = document.createElement("div");
    actions.className = "actions";
    const action = document.createElement("button");
    action.addEventListener("click", () => this._toggleRun(zone));
    const status = document.createElement("span");
    status.className = "status";
    actions.appendChild(action);
    actions.appendChild(status);
    el.appendChild(actions);
    refs.action = action;
    refs.status = status;

    this._refs[zone.zone_id] = refs;
    return el;
  }

  /* ---------- dynamic update ---------- */

  _update() {
    for (const zone of this._zones) {
      const refs = this._refs[zone.zone_id];
      if (!refs) continue;
      const st = this._stateFor(zone);
      const running = st && st.state === "on";
      const attrs = (st && st.attributes) || {};

      refs.el.classList.toggle("running", !!running);

      if (running) {
        refs.badge.hidden = false;
        const source = attrs.run_source === "scheduled" ? "scheduled" : "manual";
        refs.badgeText.textContent = `Watering · ${source}`;
      } else {
        refs.badge.hidden = true;
      }

      // Keep slider in sync unless the user is dragging it.
      if (this.shadowRoot.activeElement !== refs.slider) {
        refs.slider.value = String(zone.duration);
        refs.durVal.textContent = `${zone.duration} min`;
      }

      // Action button + status text
      if (running) {
        refs.action.className = "stop";
        refs.action.innerHTML = `<ha-icon icon="mdi:stop"></ha-icon> Stop`;
        refs.action.endsAt = attrs.ends_at || null;
      } else if (attrs.queued) {
        refs.action.className = "";
        refs.action.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> Run now`;
        refs.action.endsAt = null;
        refs.status.innerHTML = "Queued…";
      } else {
        refs.action.className = "";
        refs.action.innerHTML = `<ha-icon icon="mdi:play"></ha-icon> Run now`;
        refs.action.endsAt = null;
        refs.status.innerHTML = `${zone.duration} min manual run`;
      }
    }
    this._tick();
  }

  _tick() {
    if (!this._refs) return;
    for (const zoneId of Object.keys(this._refs)) {
      const refs = this._refs[zoneId];
      if (!refs.action || !refs.action.endsAt) continue;
      const left = Math.max(
        0,
        Math.round((new Date(refs.action.endsAt).getTime() - Date.now()) / 1000)
      );
      const m = Math.floor(left / 60);
      const s = String(left % 60).padStart(2, "0");
      refs.status.innerHTML = `Time left: <b>${m}:${s}</b>`;
    }
  }

  /* ---------- actions ---------- */

  async _toggleRun(zone) {
    const st = this._stateFor(zone);
    const running = st && st.state === "on";
    if (!zone.entity_id) {
      this._toast("Zone entity not ready yet.");
      return;
    }
    const service = running ? "turn_off" : "turn_on";
    try {
      await this._hass.callService("switch", service, {
        entity_id: zone.entity_id,
      });
    } catch (err) {
      this._toast(`Action failed: ${err.message || err}`);
    }
  }

  async _updateZone(zone, changes) {
    try {
      await this._ws({
        type: "garden_irrigation/zone/update",
        zone_id: zone.zone_id,
        ...changes,
      });
      await this._fetchZones();
    } catch (err) {
      this._toast(`Update failed: ${err.message || err}`);
    }
  }

  async _deleteZone(zone) {
    if (!confirm(`Delete zone “${zone.name}”?`)) return;
    try {
      await this._ws({
        type: "garden_irrigation/zone/delete",
        zone_id: zone.zone_id,
      });
      await this._fetchZones();
    } catch (err) {
      this._toast(`Delete failed: ${err.message || err}`);
    }
  }

  async _addSchedule(zone, time) {
    try {
      await this._ws({
        type: "garden_irrigation/schedule/add",
        zone_id: zone.zone_id,
        time,
        days: WEEKDAYS,
      });
      await this._fetchZones();
    } catch (err) {
      this._toast(`Could not add schedule: ${err.message || err}`);
    }
  }

  async _removeSchedule(zone, index) {
    try {
      await this._ws({
        type: "garden_irrigation/schedule/remove",
        zone_id: zone.zone_id,
        index,
      });
      await this._fetchZones();
    } catch (err) {
      this._toast(`Could not remove schedule: ${err.message || err}`);
    }
  }

  /* ---------- helpers ---------- */

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        detail: { message },
        bubbles: true,
        composed: true,
      })
    );
  }

  _escape(value) {
    return String(value == null ? "" : value).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        }[c])
    );
  }
}

customElements.define("garden-irrigation-card", GardenIrrigationCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "garden-irrigation-card",
  name: "Garden Irrigation",
  description: "Set up and control garden irrigation zones and schedules.",
  preview: false,
});

console.info("%c GARDEN-IRRIGATION-CARD ", "color: #03a9f4; font-weight: bold;");
