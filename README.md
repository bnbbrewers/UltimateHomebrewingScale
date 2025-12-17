# Ultimate Homebrewing Scale (UHS)

---

## Overview

Ultimate Homebrewing Scale (UHS) is an open-source DIY connected scale designed for homebrewers. Its goal is to simplify ingredient weighing (grains, hops, minerals) and enable precise counter-pressure keg filling based on weight rather than volume.

The system is designed to be **modular, affordable, and evolutive**, allowing new brewing-related use cases to be added over time.

---

## Main Features

---

### 1. Basic Scale Mode

A simple and reliable connected scale:

* Live weight display
* Manual tare at any time
* Designed to handle large brewing containers (30L bucket)

**Target specifications:**

* Maximum load: 20 kg
* Typical precision: ~5 g
* Large platform suitable for a 30 L fermentation bucket

---

### 2. Grain Assistant

The Grain Assistant helps the brewer weigh malts accurately based on a brewing recipe.

**How it works:**

1. The scale connects to the Brewfather API
2. It retrieves batches with status **Planning**
3. The user selects a batch
4. For each malt:

   * The malt name and target weight are displayed
   * The scale shows the remaining weight to add
   * Once the target is reached, it automatically moves to the next malt

This continues until all malts are weighed.

**Requirements:**

* Wi-Fi connectivity
* Brewfather API integration
* Stable and repeatable weighing

---

### 3. Hop Assistant

The Hop Assistant follows the same principle as the Grain Assistant, adapted for hops.

**Key points:**

* Step-by-step hop weighing
* Designed for smaller quantities

**Target precision:**

* 1 g preferred
* 5 g acceptable depending on hardware choice

---

### 4. Keg Filler (Counter-Pressure Filling)

This module enables automated counter-pressure keg filling using weight as the control variable.

**Principle:**

* The keg is placed on the scale
* The user selects a predefined keg (empty weight stored beforehand)
* A normally-closed solenoid valve controls the gas outlet via a spunding valve
* Filling stops automatically when the target final weight is reached

**Advantages:**

* No liquid-contact sensor (reduced infection risk)
* Works for full fills and partial top-ups
* Independent of liquid flow rate

**Filling sequence:**

1. User selects a keg
2. System asks to connect liquid and spunding
3. Solenoid valve opens
4. Filling stops slightly before 100% to account for system inertia

**Safety & reliability:**

* Normally-closed solenoid valve (failsafe)
* Manual spunding valve for stable pressure control

---

## Hardware Requirements

---

### General Considerations

* Suitable for a garage brewery environment
* Resistant to splashes (water / beer)
* Clean and integrated build (no exposed wiring)

---

### Hardware

## Controller
The M5Stack Dial offers an excellent balance between cost, integration, and usability. Its rotary encoder with push button is ideal for menu navigation during brewing sessions, even with wet hands, while the built-in screen, Wi-Fi, and ESP32 microcontroller significantly reduce wiring, enclosure complexity, and overall project cost.

* M5Dial : https://s.click.aliexpress.com/e/_c3fnF9C9
* Weight Reader I2c : https://s.click.aliexpress.com/e/_c42It9IZ
* Relay : https://s.click.aliexpress.com/e/_c3OikdVR

## Scale Platform
Using a VEVOR postal scale platform provides a cost-effective and robust solution. It is designed to handle heavy loads in wet environments and offers very easy integration thanks to its standard RJ9 connector, which simplifies wiring and makes the platform reusable without mechanical redesign.

* VEVOR scale : https://s.click.aliexpress.com/e/_c3xr1w7n
* RJ9 cable : https://s.click.aliexpress.com/e/_c2u5O1C5

## Spunding valve
This project is based on a mechanical spunding valve with a physical pressure gauge, chosen for reliability and simplicity.

The spunding valve is only required for the keg filler function.

A 12V solenoid valve is added to the system to allow automated control while using the same power supply as the controller. The solenoid valve is normally closed for safety: if the system loses power or stops unexpectedly, the filling process is immediately shut off.

This design combines the robustness of purely mechanical pressure regulation with the flexibility of electronic control, ensuring safe and reliable operation.

* Spunding valve : https://s.click.aliexpress.com/e/_c3Ccjltr
* Solenoid valve : https://s.click.aliexpress.com/e/_c2Q1v85j
* 1/8 Adapter : https://s.click.aliexpress.com/e/_c3iy7LDR

## Integration Box
TODO




