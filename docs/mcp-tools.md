# MCP tool reference

49 tools. Schemas are generated from `mcp_bridge/catalog.py`. Required fields are explicit; omitted optional values use upstream defaults. IDs and coordinates in examples are placeholders. See [the full capability guide](mcp.md) before making changes.

## carla_status

Read live runtime, actors, routes, vehicle controls, weather, signals, sensors, occupancy, GPU timings and operation progress.

Access: read-only. Route: `/api/status`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_catalog

Read installed vehicle/pedestrian models and sensor blueprint attributes.

Access: read-only. Route: `/api/catalog`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_map

Read OpenDRIVE-derived roads, lane directions/turns, sidewalks, walking points, spawn points and surveyed parking including exclusions.

Access: read-only. Route: `/api/map`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_configuration

Export the complete reusable scenario configuration. This request is serialized with simulator operations.

Access: read-only. Route: `/api/configuration`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_sessions

List recording manifests, frame counts, status and ROS bag availability.

Access: read-only. Route: `/api/sessions`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_log

Read the last 6 KB of simulator output.

Access: read-only. Route: `/api/log`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_opendrive

Read the original OpenDRIVE XML. Surveyed parking and pedestrian overlays are in carla_map, not written into this XML.

Access: read-only. Route: `/api/map.xodr`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_capabilities

Read the WebUI feature mapping, tool schemas and examples.

Access: read-only. Route: `adapter operation`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_latency

Measure one MCP-bridge-to-WebUI status round trip in milliseconds; this is not browser latency or simulation speed.

Access: read-only. Route: `adapter operation`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_start

Start the owned CARLA simulator group asynchronously. Poll carla_status until connected; do not repeat start.

Access: mutation. Route: `/api/command/start`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "gpus": {
      "type": "string",
      "enum": [
        "auto",
        "3",
        "0,1,2,3"
      ]
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "gpus": "auto"
}
```

## carla_connect

Connect to the existing local CARLA on port 2000. No other client may own its clock.

Access: mutation. Route: `/api/command/connect`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_shutdown

Stop the owned CARLA group and workers, or disconnect an external simulator. This destroys the current owned runtime; export configuration first if needed.

Access: mutation. Route: `/api/command/shutdown`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_run

Advance the shared synchronous simulation continuously, or resume native replay.

Access: mutation. Route: `/api/command/run`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_pause

Pause the shared simulation clock; sensor previews may still read the last completed sample.

Access: mutation. Route: `/api/command/pause`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_step

Advance one synchronous frame. Do this while paused for controlled stepping; setup operations may also advance frames.

Access: mutation. Route: `/api/command/step`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_spawn

Spawn an ego, background vehicle or pedestrian. Ego omission of sensors adds six defaults. For parked placement use background role and parking_space; spawn may be omitted in that case. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/spawn`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "role": {
      "type": "string",
      "enum": [
        "ego",
        "background",
        "pedestrian"
      ]
    },
    "model": {
      "type": "string",
      "minLength": 1
    },
    "planner": {
      "type": "string",
      "enum": [
        "tm",
        "external"
      ]
    },
    "spawn": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        },
        "yaw": {
          "type": "number"
        },
        "pitch": {
          "type": "number"
        },
        "roll": {
          "type": "number"
        },
        "parking_space": {
          "type": "string",
          "minLength": 1
        }
      },
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false
    },
    "destination": {
      "anyOf": [
        {
          "type": "object",
          "properties": {
            "x": {
              "type": "number"
            },
            "y": {
              "type": "number"
            },
            "z": {
              "type": "number"
            },
            "yaw": {
              "type": "number"
            },
            "pitch": {
              "type": "number"
            },
            "roll": {
              "type": "number"
            },
            "parking_space": {
              "type": "string",
              "minLength": 1
            }
          },
          "required": [
            "x",
            "y"
          ],
          "additionalProperties": false
        },
        {
          "type": "null"
        }
      ]
    },
    "parking_space": {
      "type": "string",
      "minLength": 1
    },
    "sensors": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_]{0,39}$"
          },
          "type": {
            "type": "string",
            "enum": [
              "sensor.camera.rgb",
              "sensor.camera.depth",
              "sensor.camera.semantic_segmentation",
              "sensor.camera.instance_segmentation",
              "sensor.camera.normals",
              "sensor.camera.optical_flow",
              "sensor.lidar.ray_cast",
              "sensor.lidar.ray_cast_semantic",
              "sensor.other.radar",
              "sensor.other.imu",
              "sensor.other.gnss"
            ]
          },
          "mount": {
            "type": "object",
            "properties": {
              "x": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "y": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "z": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "yaw": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "pitch": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "roll": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "attributes": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            }
          }
        },
        "required": [
          "name",
          "type",
          "mount",
          "attributes"
        ],
        "additionalProperties": false
      },
      "maxItems": 16
    }
  },
  "required": [
    "role",
    "model"
  ],
  "additionalProperties": false,
  "anyOf": [
    {
      "required": [
        "spawn"
      ]
    },
    {
      "required": [
        "parking_space"
      ]
    }
  ]
}
```

Example arguments (resolve IDs/points first):

```json
{
  "role": "ego",
  "model": "vehicle.lincoln.mkz_interior",
  "planner": "tm",
  "spawn": {
    "x": 0,
    "y": 0
  }
}
```

## carla_delete_actor

Remove a managed actor and its attached sensors/walker controller. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/delete`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 52
}
```

## carla_destination

Replace the active goal immediately, including during recording. Road points snap to lanes; parking_space selects a validated bay. TM drives reverse parking; external ego receives an exact goal without control takeover. Pedestrians use walkable points. Rejects native replay.

Access: mutation. Route: `/api/command/destination`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "point": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        },
        "yaw": {
          "type": "number"
        },
        "pitch": {
          "type": "number"
        },
        "roll": {
          "type": "number"
        },
        "parking_space": {
          "type": "string",
          "minLength": 1
        }
      },
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false
    },
    "arrival_tolerance": {
      "type": "number",
      "minimum": 0.25,
      "maximum": 3
    }
  },
  "required": [
    "id",
    "point"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 52,
  "point": {
    "x": 8,
    "y": 63,
    "parking_space": "P024"
  }
}
```

## carla_pedestrian_path

Check pedestrian route reachability without changing the destination.

Access: read-only. Route: `/api/command/pedestrian-path`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "point": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        },
        "yaw": {
          "type": "number"
        },
        "pitch": {
          "type": "number"
        },
        "roll": {
          "type": "number"
        },
        "parking_space": {
          "type": "string",
          "minLength": 1
        }
      },
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "id",
    "point"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 60,
  "point": {
    "x": 0,
    "y": 0
  }
}
```

## carla_control

Apply external ego throttle, steer, brake and reverse through vehicle physics. Existing external control watchdog brakes after one wall-clock second. Use a dedicated HTTP/ROS control loop for continuous driving; MCP is not a real-time controller.

Access: mutation. Route: `/api/command/control`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "throttle": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "steer": {
      "type": "number",
      "minimum": -1,
      "maximum": 1
    },
    "brake": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "reverse": {
      "type": "boolean"
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 52,
  "throttle": 0,
  "steer": 0,
  "brake": 1,
  "reverse": false
}
```

## carla_convert_scene_vehicles

Convert remaining native scenery vehicles to managed background actors; reports substitutions and failures. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/convert-scene-vehicles`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_move_parked_to_road

Explicitly reposition a parked scene vehicle onto a road and enable Traffic Manager. This is placement, not a driven departure; use destination for physical departure. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/parked-to-road`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "point": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        },
        "yaw": {
          "type": "number"
        },
        "pitch": {
          "type": "number"
        },
        "roll": {
          "type": "number"
        },
        "parking_space": {
          "type": "string",
          "minLength": 1
        }
      },
      "required": [
        "x",
        "y"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "id",
    "point"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 34,
  "point": {
    "x": 0,
    "y": 0
  }
}
```

## carla_reload_parking

Reload validated on-disk parking annotations without restarting the world. Stop recording and replay first.

Access: mutation. Route: `/api/command/reload-parking`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_configure_sensors

Replace the entire ego loadout; empty list removes all sensors. Mount is vehicle-local metres/degrees; attributes are strings. May allocate GPU workers and warm cameras for 30 frames. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/sensors`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "sensors": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "pattern": "^[a-z][a-z0-9_]{0,39}$"
          },
          "type": {
            "type": "string",
            "enum": [
              "sensor.camera.rgb",
              "sensor.camera.depth",
              "sensor.camera.semantic_segmentation",
              "sensor.camera.instance_segmentation",
              "sensor.camera.normals",
              "sensor.camera.optical_flow",
              "sensor.lidar.ray_cast",
              "sensor.lidar.ray_cast_semantic",
              "sensor.other.radar",
              "sensor.other.imu",
              "sensor.other.gnss"
            ]
          },
          "mount": {
            "type": "object",
            "properties": {
              "x": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "y": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "z": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "yaw": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "pitch": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              },
              "roll": {
                "type": "number",
                "minimum": -360,
                "maximum": 360
              }
            },
            "required": [],
            "additionalProperties": false
          },
          "attributes": {
            "type": "object",
            "additionalProperties": {
              "type": "string"
            }
          }
        },
        "required": [
          "name",
          "type",
          "mount",
          "attributes"
        ],
        "additionalProperties": false
      },
      "maxItems": 16
    }
  },
  "required": [
    "id",
    "sensors"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 52,
  "sensors": []
}
```

## carla_weather

Apply any subset of the supported weather fields to the synchronized scene. Works running or paused; stop recording and native replay first. Advances a synchronization frame.

Access: mutation. Route: `/api/command/weather`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "cloudiness": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "precipitation": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "precipitation_deposits": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "wind_intensity": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "fog_density": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "wetness": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "dust_storm": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "fog_falloff": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "scattering_intensity": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "mie_scattering_scale": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "rayleigh_scattering_scale": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "sun_azimuth_angle": {
      "type": "number",
      "minimum": 0,
      "maximum": 360
    },
    "sun_altitude_angle": {
      "type": "number",
      "minimum": -90,
      "maximum": 90
    },
    "fog_distance": {
      "type": "number",
      "minimum": 0,
      "maximum": 10000
    }
  },
  "required": [],
  "additionalProperties": false,
  "minProperties": 1
}
```

Example arguments (resolve IDs/points first):

```json
{
  "sun_altitude_angle": -25,
  "cloudiness": 20,
  "precipitation": 0
}
```

## carla_traffic_light

Set native approach colour, hold its intersection, resume cycle, or edit durations. Movement programs must be disabled and clearance finished first. Holding sets other approaches red. Works running or paused; stop recording and native replay first. Advances a synchronization frame.

Access: mutation. Route: `/api/command/traffic-light`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "integer",
      "minimum": 1
    },
    "operation": {
      "type": "string",
      "enum": [
        "state",
        "timing",
        "resume"
      ]
    },
    "state": {
      "type": "string",
      "enum": [
        "Red",
        "Yellow",
        "Green",
        "Off"
      ]
    },
    "hold": {
      "type": "boolean"
    },
    "scope": {
      "type": "string",
      "enum": [
        "signal",
        "intersection"
      ]
    },
    "green_time": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 600
    },
    "yellow_time": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 600
    },
    "red_time": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 600
    }
  },
  "required": [
    "id",
    "operation"
  ],
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "operation": {
            "const": "state"
          }
        }
      },
      "then": {
        "required": [
          "state"
        ]
      }
    },
    {
      "if": {
        "properties": {
          "operation": {
            "const": "timing"
          }
        }
      },
      "then": {
        "required": [
          "green_time",
          "yellow_time",
          "red_time"
        ]
      }
    }
  ]
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": 10,
  "operation": "state",
  "state": "Red",
  "hold": true
}
```

## carla_movement_program

Enable/update protected and permissive left/straight/right phases, hold, resume, select phase or disable. Conflicting protected paths and unsupported turns are rejected. Edits use yellow/all-red clearance; phase index is zero-based. Works running or paused; stop recording and native replay first. Advances a synchronization frame.

Access: mutation. Route: `/api/command/movement-program`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "group_id": {
      "type": "integer",
      "minimum": 1
    },
    "operation": {
      "type": "string",
      "enum": [
        "enable",
        "update",
        "disable",
        "hold",
        "resume",
        "phase"
      ]
    },
    "phases": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "duration": {
            "type": "number",
            "minimum": 0.5,
            "maximum": 600
          },
          "states": {
            "type": "object",
            "additionalProperties": {
              "type": "object",
              "properties": {
                "left": {
                  "type": "string",
                  "enum": [
                    "Stop",
                    "Protected",
                    "Permissive",
                    "Off"
                  ]
                },
                "straight": {
                  "type": "string",
                  "enum": [
                    "Stop",
                    "Protected",
                    "Permissive",
                    "Off"
                  ]
                },
                "right": {
                  "type": "string",
                  "enum": [
                    "Stop",
                    "Protected",
                    "Permissive",
                    "Off"
                  ]
                }
              },
              "required": [],
              "additionalProperties": false
            }
          }
        },
        "required": [
          "duration",
          "states"
        ],
        "additionalProperties": false
      },
      "minItems": 1,
      "maxItems": 16
    },
    "yellow_time": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 30
    },
    "all_red_time": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 30
    },
    "index": {
      "type": "integer",
      "minimum": 0,
      "maximum": 15
    },
    "hold": {
      "type": "boolean"
    }
  },
  "required": [
    "group_id",
    "operation"
  ],
  "additionalProperties": false,
  "allOf": [
    {
      "if": {
        "properties": {
          "operation": {
            "const": "phase"
          }
        }
      },
      "then": {
        "required": [
          "index"
        ]
      }
    }
  ]
}
```

Example arguments (resolve IDs/points first):

```json
{
  "group_id": 10,
  "operation": "enable",
  "yellow_time": 3,
  "all_red_time": 2
}
```

## carla_network_timing

Select independent, coordinated common-cycle/offset, or demand-adaptive timing. Coordinated/adaptive requires fully applied movement plans at every intersection. Works running or paused; stop recording and native replay first. Advances a synchronization frame.

Access: mutation. Route: `/api/command/network-timing`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "mode": {
      "type": "string",
      "enum": [
        "independent",
        "coordinated",
        "adaptive"
      ]
    },
    "cycle_time": {
      "type": "number",
      "minimum": 1,
      "maximum": 3600
    },
    "offsets": {
      "type": "object",
      "additionalProperties": {
        "type": "number",
        "minimum": 0,
        "maximum": 3600
      }
    },
    "min_green": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 120
    },
    "max_green": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 600
    },
    "gap": {
      "type": "number",
      "minimum": 0.5,
      "maximum": 15
    },
    "distance": {
      "type": "number",
      "minimum": 5,
      "maximum": 100
    }
  },
  "required": [
    "mode"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "mode": "adaptive",
  "min_green": 5,
  "max_green": 30,
  "gap": 2,
  "distance": 40
}
```

## carla_configure_schedule

Replace the full flows/events schedule. Stop the schedule first. Uses zero-based map spawn/walking point indices and simulation-relative seconds. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/authoring-configure`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "config": {
      "type": "object",
      "properties": {
        "flows": {
          "type": "array",
          "maxItems": 32,
          "items": {
            "type": "object",
            "properties": {
              "id": {
                "type": "string",
                "minLength": 1
              },
              "model": {
                "type": "string",
                "minLength": 1
              },
              "spawn": {
                "type": "integer",
                "minimum": 0
              },
              "destination": {
                "type": "integer",
                "minimum": 0
              },
              "start": {
                "type": "number",
                "minimum": 0,
                "maximum": 86400
              },
              "interval": {
                "type": "number",
                "minimum": 1,
                "maximum": 3600
              },
              "count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000
              },
              "remove_arrived": {
                "type": "boolean"
              }
            },
            "required": [
              "id",
              "model",
              "spawn",
              "destination",
              "count"
            ],
            "additionalProperties": false
          }
        },
        "events": {
          "type": "array",
          "maxItems": 256,
          "items": {
            "type": "object",
            "properties": {
              "id": {
                "type": "string",
                "minLength": 1
              },
              "time": {
                "type": "number",
                "minimum": 0,
                "maximum": 86400
              },
              "action": {
                "type": "string",
                "enum": [
                  "spawn_vehicle",
                  "spawn_pedestrian",
                  "destination",
                  "weather",
                  "signal_phase",
                  "signal_hold",
                  "signal_resume"
                ]
              },
              "model": {
                "type": "string",
                "minLength": 1
              },
              "spawn": {
                "type": "integer",
                "minimum": 0
              },
              "destination": {
                "type": "integer",
                "minimum": 0
              },
              "actor": {
                "type": [
                  "string",
                  "integer"
                ]
              },
              "preset": {
                "type": "string",
                "enum": [
                  "clear",
                  "cloudy",
                  "rain",
                  "sunset",
                  "night"
                ]
              },
              "group_id": {
                "type": "integer",
                "minimum": 1
              },
              "index": {
                "type": "integer",
                "minimum": 0
              }
            },
            "required": [
              "id",
              "action"
            ],
            "additionalProperties": false
          }
        }
      },
      "required": [],
      "additionalProperties": false
    }
  },
  "required": [
    "config"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "config": {
    "flows": [],
    "events": [
      {
        "id": "nightfall",
        "time": 30,
        "action": "weather",
        "preset": "night"
      }
    ]
  }
}
```

## carla_start_schedule

Arm the saved schedule relative to current simulation time. Run or step afterward to execute departures/events. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/authoring-start`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_stop_schedule

Stop future schedule execution. Already spawned actors remain; pending automatic arrival cleanup also stops.

Access: mutation. Route: `/api/command/authoring-stop`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_gpu_profile

Apply automatic or up-to-N GPU worker policy; may recreate sensor streams. Preserves sensor quality. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/gpu-profile`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "profile": {
      "type": "string",
      "enum": [
        "auto",
        "1",
        "2",
        "3",
        "4"
      ]
    }
  },
  "required": [
    "profile"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "profile": "auto"
}
```

## carla_gpu_benchmark

Measure GPU worker counts with three 50-frame windows per count. Advances the evolving scene, recreates sensor streams, and can take several minutes. Preserves quality. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/gpu-benchmark`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_record_start

Arm native recorder plus exact state/raw sensor capture and optional ROS 2 bag. Requires live mode, ROS and at least 5 GiB free. Run or step to capture.

Access: mutation. Route: `/api/command/record-start`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "rosbag": {
      "type": "boolean"
    }
  },
  "required": [],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "rosbag": true
}
```

## carla_record_stop

Finalize the recording, ROS bag and integrity manifest.

Access: mutation. Route: `/api/command/record-stop`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_replay_native

Replace current actors with a completed recording in native CARLA replay. Requires owned simulator; regenerated sensors are not bit-identical originals. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/replay-native`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "start": {
      "type": "number",
      "minimum": 0
    },
    "autoplay": {
      "type": "boolean"
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "id": "REPLACE_WITH_SESSION_ID",
  "start": 0,
  "autoplay": true
}
```

## carla_replay_stop

Stop native replay and asynchronously restart owner and CARLA into a clean live scene. Poll status through temporary API unavailability; existing replay actors are discarded.

Access: mutation. Route: `/api/command/replay-stop`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_restore_configuration

Restore an exported configuration into an empty managed scene. Not a physics checkpoint. Restores actors/sensors/weather/signals/parking/schedule; leaves simulation paused. Requires paused live simulation with recording stopped.

Access: mutation. Route: `/api/command/restore-configuration`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "configuration": {
      "type": "object"
    }
  },
  "required": [
    "configuration"
  ],
  "additionalProperties": false
}
```

## carla_recover

Restart a failed owned simulator using its saved recovery configuration. Only available in error state; actor IDs and time can change. Poll status until ready.

Access: mutation. Route: `/api/recover`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_session_frame

Read exact recorded states and sensor file references by zero-based recording index.

Access: read-only. Route: `/api/sessions/{session_id}/frame/{index}`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "index": {
      "type": "integer",
      "minimum": 0
    }
  },
  "required": [
    "session_id",
    "index"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "session_id": "REPLACE_WITH_SESSION_ID",
  "index": 0
}
```

## carla_session_files

List recorded session files and byte sizes.

Access: read-only. Route: `/api/sessions/{session_id}/files`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    }
  },
  "required": [
    "session_id"
  ],
  "additionalProperties": false
}
```

## carla_verify_session

Verify a stopped recording: hashes, frame/sample continuity and timestamps. Saves verification.json; does not re-simulate.

Access: mutation. Route: `/api/sessions/{session_id}/verify`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    }
  },
  "required": [
    "session_id"
  ],
  "additionalProperties": false
}
```

## carla_compare_sessions

Compare stopped recordings by configured actor order and recording-relative frames, including trajectories and signals. Separate from byte integrity.

Access: read-only. Route: `/api/compare`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "reference": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "candidate": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    }
  },
  "required": [
    "reference",
    "candidate"
  ],
  "additionalProperties": false
}
```

## carla_sensor_preview

Fetch ONE latest requested sensor preview only. Image default returns an MCP image plus frame/timestamp metadata; points returns bounded binary as an embedded resource; IMU/GNSS return JSON. after suppresses identical frames. Does not run or subscribe to sensors.

Access: read-only. Route: `/api/preview/{sensor_id}`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "sensor_id": {
      "type": "integer",
      "minimum": 1
    },
    "width": {
      "type": "integer",
      "minimum": 160,
      "maximum": 960
    },
    "after": {
      "type": "integer",
      "minimum": -1
    },
    "format": {
      "type": "string",
      "enum": [
        "image",
        "points"
      ]
    },
    "point_limit": {
      "type": "integer",
      "minimum": 512,
      "maximum": 12000
    }
  },
  "required": [
    "sensor_id"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "sensor_id": 53,
  "width": 640,
  "after": -1
}
```

## carla_recorded_preview

Read the saved frame’s first RGB camera as a 640-pixel JPEG. Use session files for other original camera samples.

Access: read-only. Route: `/api/sessions/{session_id}/preview/{index}`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "index": {
      "type": "integer",
      "minimum": 0
    }
  },
  "required": [
    "session_id",
    "index"
  ],
  "additionalProperties": false
}
```

## carla_session_file

Read one session file, capped at 2 MiB. Binary is an embedded resource; large files return an error with a download URL. Paths must be relative and traversal-free.

Access: read-only. Route: `/api/sessions/{session_id}/files/{filename}`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "filename": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "session_id",
    "filename"
  ],
  "additionalProperties": false
}
```

## carla_download_links

Get direct WebUI links without downloading archives/raw sensor datasets into model context. kind=session requires session_id; optional filename chooses one file.

Access: read-only. Route: `adapter operation`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "kind": {
      "type": "string",
      "enum": [
        "session",
        "opendrive",
        "parking_review",
        "webui"
      ]
    },
    "session_id": {
      "type": "string",
      "pattern": "^[A-Za-z0-9_-]+$",
      "maxLength": 128
    },
    "filename": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "kind"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "kind": "parking_review"
}
```

## carla_scene_manifest

Read the current map’s exported browser geometry/texture manifest and base URL without loading the meshes.

Access: read-only. Route: `adapter operation`.

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "required": [],
  "additionalProperties": false
}
```

## carla_inspect

Read selected top-level status/map/catalog/configuration fields. Page a single array or object field to keep large maps out of model context. No scene mutation.

Access: read-only. Route: `adapter operation`.

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "enum": [
        "status",
        "map",
        "catalog",
        "configuration"
      ]
    },
    "fields": {
      "type": "array",
      "items": {
        "type": "string",
        "minLength": 1
      },
      "minItems": 1
    },
    "offset": {
      "type": "integer",
      "minimum": 0
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 500
    }
  },
  "required": [
    "source",
    "fields"
  ],
  "additionalProperties": false
}
```

Example arguments (resolve IDs/points first):

```json
{
  "source": "map",
  "fields": [
    "parking_spaces"
  ],
  "offset": 0,
  "limit": 10
}
```

## Cabin preset objects

The WebUI draft definitions below use JavaScript object notation. Convert to JSON, preserving mount and attributes, and include them in the complete `sensors` list. `coverage` adds all three with unique names.

```javascript
{
 overview:{name:'cabin_overview',type:'sensor.camera.rgb',mount:{x:.55,y:0,z:1.2,yaw:180,pitch:-8,roll:0},attributes:{image_size_x:'960',image_size_y:'600',fov:'120',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}},
 dashboard:{name:'cabin_dashboard',type:'sensor.camera.rgb',mount:{x:-.20,y:0,z:1.25,yaw:0,pitch:-16},attributes:{image_size_x:'960',image_size_y:'600',fov:'100',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}},
 rear:{name:'cabin_rear_seats',type:'sensor.camera.rgb',mount:{x:-.43,y:.05,z:1.22,yaw:180,pitch:-15},attributes:{image_size_x:'960',image_size_y:'600',fov:'100',post_process_profile:'CabinObservation',lens_k:'0',use_ray_tracing:'false'}}
}
```
