using System.IO;
using DisasterSurvival.Core;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace DisasterSurvival.EditorTools
{
    /// <summary>
    /// Menu: Tools > Disaster Survival > Build Demo Scene.
    /// Builds a playable greybox arena: player, three bots, rescue station, bunker, rooftop, radios,
    /// emergency kit, tornado, flood water, lava, fire front, collapse zones, supply drops and the HUD.
    /// </summary>
    public static class DemoSceneBuilder
    {
        const string Folder = "Assets/DisasterSurvival/Demo";
        static string _matFolder;

        [MenuItem("Tools/Disaster Survival/Build Demo Scene")]
        public static void Build()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            EnsureFolder(Folder);
            _matFolder = Folder + "/Materials";
            EnsureFolder(_matFolder);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.DefaultGameObjects, NewSceneMode.Single);

            var grass = Mat("Grass", new Color(0.33f, 0.5f, 0.27f));
            var concrete = Mat("Concrete", new Color(0.6f, 0.6f, 0.58f));
            var dark = Mat("Dark", new Color(0.16f, 0.17f, 0.19f));
            var green = Mat("RescueGreen", new Color(0.2f, 0.75f, 0.35f));
            var red = Mat("KitRed", new Color(0.85f, 0.15f, 0.12f));
            var yellow = Mat("SignalYellow", new Color(1f, 0.82f, 0.2f));
            var water = Mat("Water", new Color(0.15f, 0.4f, 0.75f));
            var lava = Mat("Lava", new Color(1f, 0.35f, 0.05f));
            var storm = Mat("Storm", new Color(0.35f, 0.37f, 0.42f));
            var ice = Mat("Ice", new Color(0.75f, 0.9f, 1f));
            var wood = Mat("Wood", new Color(0.55f, 0.38f, 0.22f));
            var blue = Mat("PlayerBlue", new Color(0.2f, 0.45f, 0.95f));

            // ---------------- ground and buildings
            Box("Ground", null, new Vector3(0, -0.5f, 0), new Vector3(170, 1, 170), grass);

            // rescue station on a raised platform, reachable by a ramp, safe from normal floods
            var stationRoot = new GameObject("Rescue Station").transform;
            Box("Platform", stationRoot, new Vector3(0, 1.3f, 42), new Vector3(14, 2.6f, 12), concrete);
            Box("Pad", stationRoot, new Vector3(0, 2.65f, 42), new Vector3(10, 0.1f, 8), green);
            Ramp("Station Ramp", stationRoot, new Vector3(0, 0, 26), new Vector3(0, 2.6f, 36), 5f, concrete);
            var stationZone = TriggerZone("Rescue Zone", stationRoot, new Vector3(0, 4.2f, 42), new Vector3(10, 3, 8));
            var sz = stationZone.AddComponent<MissionZone>();
            sz.zoneId = ContentLibrary.RescueStation;
            var drop = new GameObject("Drop Point").transform;
            drop.SetParent(stationRoot);
            drop.position = new Vector3(3, 3.2f, 44);

            // bunker with an automatic door
            var bunker = new GameObject("Bunker").transform;
            Box("Wall Back", bunker, new Vector3(-30, 2, -5), new Vector3(10, 4, 0.5f), concrete);
            Box("Wall Left", bunker, new Vector3(-35, 2, -10), new Vector3(0.5f, 4, 10), concrete);
            Box("Wall Right", bunker, new Vector3(-25, 2, -10), new Vector3(0.5f, 4, 10), concrete);
            Box("Wall Front L", bunker, new Vector3(-33.25f, 2, -15), new Vector3(3.5f, 4, 0.5f), concrete);
            Box("Wall Front R", bunker, new Vector3(-26.75f, 2, -15), new Vector3(3.5f, 4, 0.5f), concrete);
            Box("Roof", bunker, new Vector3(-30, 4.25f, -10), new Vector3(10.5f, 0.5f, 10.5f), dark);
            var door = Box("Door", bunker, new Vector3(-30, 1.6f, -15), new Vector3(3, 3.2f, 0.4f), dark);
            var bd = door.AddComponent<BunkerDoor>();
            var powerLight = Box("Power Out Light", door.transform, new Vector3(-30, 3.5f, -15.4f), new Vector3(0.6f, 0.3f, 0.1f), red);
            Object.DestroyImmediate(powerLight.GetComponent<Collider>());
            bd.powerOutIndicator = powerLight;
            var bz = TriggerZone("Bunker Zone", bunker, new Vector3(-30, 1.5f, -10), new Vector3(9, 3, 9)).AddComponent<MissionZone>();
            bz.zoneId = ContentLibrary.Bunker;
            bz.acceptsItems = new string[0];
            bz.acceptsInjured = false;

            // tall building with a ramp to the rooftop
            var tower = new GameObject("Tower").transform;
            Box("Tower Block", tower, new Vector3(32, 4, 0), new Vector3(12, 8, 12), concrete);
            Ramp("Tower Ramp", tower, new Vector3(6, 0, 0), new Vector3(26, 8, 0), 4f, wood);
            var rz = TriggerZone("Rooftop Zone", tower, new Vector3(32, 9.5f, 0), new Vector3(12, 3, 12)).AddComponent<MissionZone>();
            rz.zoneId = ContentLibrary.Rooftop;
            rz.acceptsItems = new string[0];
            rz.acceptsInjured = false;

            // houses that collapse during aftershocks
            var houses = new GameObject("Houses").transform;
            foreach (var pos in new[] { new Vector3(-42, 0, 28), new Vector3(14, 0, -28), new Vector3(46, 0, 34) })
            {
                Box("House", houses, pos + new Vector3(0, 2.5f, 0), new Vector3(8, 5, 8), wood);
                var hz = TriggerZone("Collapse Zone", houses, pos + new Vector3(0, 2, 0), new Vector3(13, 4, 13)).AddComponent<HazardVolume>();
                hz.onlyDuring = EventEffect.GroundShaking;
                hz.cause = "was buried by a collapsing house";
                hz.secondsToKill = 2.5f;
            }

            // ---------------- mission objects
            var radios = new GameObject("Emergency Radios").transform;
            foreach (var pos in new[] { new Vector3(-20, 0, 30), new Vector3(25, 0, 28), new Vector3(48, 0, -30), new Vector3(-48, 0, -35), new Vector3(0, 0, -45) })
            {
                var r = Box("Radio", radios, pos + new Vector3(0, 0.75f, 0), new Vector3(1, 1.5f, 1), dark);
                var er = r.AddComponent<EmergencyRadio>();
                var idle = Box("Idle Light", r.transform, pos + new Vector3(0, 1.7f, 0), new Vector3(0.4f, 0.4f, 0.4f), yellow);
                Object.DestroyImmediate(idle.GetComponent<Collider>());
                var used = Box("Used Light", r.transform, pos + new Vector3(0, 1.7f, 0), new Vector3(0.4f, 0.4f, 0.4f), green);
                Object.DestroyImmediate(used.GetComponent<Collider>());
                used.SetActive(false);
                er.idleIndicator = idle;
                er.usedIndicator = used;
            }

            var kit = Box("Emergency Kit", null, new Vector3(-12, 0.4f, -26), new Vector3(0.8f, 0.6f, 0.6f), red);
            kit.AddComponent<Rigidbody>().mass = 5f;
            kit.AddComponent<DeliveryItem>().itemId = ContentLibrary.EmergencyKit;

            // ---------------- hazards per disaster
            var tornado = new GameObject("Tornado").transform;
            tornado.position = new Vector3(-55, 0, 55);
            var funnel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            funnel.name = "Funnel";
            funnel.transform.SetParent(tornado, false);
            funnel.transform.localPosition = new Vector3(0, 15, 0);
            funnel.transform.localScale = new Vector3(7, 15, 7);
            funnel.GetComponent<Renderer>().sharedMaterial = storm;
            Object.DestroyImmediate(funnel.GetComponent<Collider>());
            var tc = tornado.gameObject.AddComponent<CapsuleCollider>();
            tc.isTrigger = true; tc.radius = 4.5f; tc.height = 30f; tc.center = new Vector3(0, 15, 0);
            tornado.gameObject.AddComponent<Rigidbody>().isKinematic = true;
            tornado.gameObject.AddComponent<HazardVolume>().cause = "was swept away by the tornado";
            var tm = tornado.gameObject.AddComponent<HazardMover>();
            tm.areaRadius = 60f;
            tornado.gameObject.AddComponent<DisasterSpecific>().activeDuring = new[] { DisasterType.Tornado };

            var fire = Box("Fire Front", null, new Vector3(0, 1.5f, -70), new Vector3(40, 3, 4), lava);
            fire.GetComponent<Collider>().isTrigger = true;
            fire.AddComponent<Rigidbody>().isKinematic = true;
            fire.AddComponent<HazardVolume>().cause = "was caught by the fire";
            var fm = fire.AddComponent<HazardMover>();
            fm.speed = 2.5f; fm.spinDegreesPerSecond = 0f; fm.areaRadius = 55f;
            fire.AddComponent<DisasterSpecific>().activeDuring = new[] { DisasterType.Wildfire };

            var floodGo = Box("Flood Water", null, new Vector3(0, -3, 0), new Vector3(168, 4, 168), water);
            Object.DestroyImmediate(floodGo.GetComponent<Collider>());
            var fw = floodGo.AddComponent<FloodWater>();
            fw.baseLevel = -1f; fw.floodLevel = 2.3f;
            floodGo.AddComponent<DisasterSpecific>().activeDuring = new[] { DisasterType.Flood, DisasterType.Tornado, DisasterType.Earthquake };

            var lavaGo = Box("Lava", null, new Vector3(0, -3, 0), new Vector3(168, 4, 168), lava);
            Object.DestroyImmediate(lavaGo.GetComponent<Collider>());
            var lw = lavaGo.AddComponent<FloodWater>();
            lw.baseLevel = -1f; lw.floodLevel = 2.4f; lw.constantRisePerMinute = 0.5f; lw.secondsToDrown = 1.5f; lw.headHeight = 0.3f; lw.cause = "was caught by the lava";
            lavaGo.AddComponent<DisasterSpecific>().activeDuring = new[] { DisasterType.Volcano };

            var iceField = Box("Ice Field", null, new Vector3(0, 0.05f, -10), new Vector3(30, 0.1f, 20), ice);
            var iceTrigger = (BoxCollider)iceField.GetComponent<Collider>();
            iceTrigger.isTrigger = true;
            iceTrigger.size = new Vector3(1f, 20f, 1f);      // 2 m high, so standing players are inside
            iceTrigger.center = new Vector3(0f, 10f, 0f);
            var ih = iceField.AddComponent<HazardVolume>();
            ih.cause = "froze on the ice"; ih.secondsToKill = 8f;
            iceField.AddComponent<DisasterSpecific>().activeDuring = new[] { DisasterType.Blizzard };

            var crate = Box("Supply Crate Template", null, new Vector3(0, -20, 0), new Vector3(1.4f, 1.2f, 1.4f), yellow);
            crate.AddComponent<Rigidbody>().mass = 20f;
            crate.AddComponent<SupplyCrate>();
            crate.SetActive(false);

            // ---------------- players
            var spawns = new GameObject("Spawn Points").transform;
            var spawnList = new Transform[4];
            for (int i = 0; i < 4; i++)
            {
                var s = new GameObject("Spawn " + (i + 1)).transform;
                s.SetParent(spawns);
                s.position = new Vector3(-6 + i * 4, 1.1f, 12);
                spawnList[i] = s;
            }

            var player = Capsule("Player", new Vector3(-6, 1.1f, 12), blue);
            var pc = player.AddComponent<SimplePlayerController>();
            var pivot = new GameObject("Camera Pivot").transform;
            pivot.SetParent(player.transform, false);
            pivot.localPosition = new Vector3(0, 0.7f, 0);
            pc.cameraPivot = pivot;
            var cam = Camera.main != null ? Camera.main.gameObject : new GameObject("Main Camera", typeof(Camera));
            cam.transform.SetParent(pivot, false);
            cam.transform.localPosition = new Vector3(0, 1.2f, -6.5f);
            cam.transform.localRotation = Quaternion.Euler(8f, 0, 0);
            var pa = player.AddComponent<PlayerAgent>();
            pa.playerId = "local_player";
            pa.displayName = "You";
            pa.isLocalPlayer = true;
            pa.disableWhenDown = new Behaviour[] { pc };
            pa.hideWhenDead = new[] { player.GetComponent<Renderer>() };

            var botColors = new[] { new Color(0.95f, 0.45f, 0.2f), new Color(0.6f, 0.35f, 0.9f), new Color(0.2f, 0.75f, 0.7f) };
            var botNames = new[] { "Ava", "Max", "Kim" };
            var botHelp = new[] { 0.8f, 0.35f, 0.6f };
            for (int i = 0; i < 3; i++)
            {
                var bot = Capsule("Bot " + botNames[i], new Vector3(-2 + i * 4, 1.1f, 12), Mat("Bot" + botNames[i], botColors[i]));
                var a = bot.AddComponent<PlayerAgent>();
                a.playerId = "bot_" + botNames[i].ToLowerInvariant();
                a.displayName = botNames[i];
                a.isLocalPlayer = false;
                a.hideWhenDead = new[] { bot.GetComponent<Renderer>() };
                bot.AddComponent<SimpleBot>().helpfulness = botHelp[i];
            }

            // ---------------- game manager
            var gmGo = new GameObject("Disaster Game Manager");
            var gm = gmGo.AddComponent<DisasterGameManager>();
            gm.spawnPoints = spawnList;
            gm.rescueDropPoint = drop;
            gmGo.AddComponent<DisasterHud>();
            gmGo.AddComponent<VisibilityEffect>();
            var sd = gmGo.AddComponent<SupplyDrop>();
            sd.cratePrefab = crate.GetComponent<SupplyCrate>();
            sd.areaRadius = 45f;

            var path = Folder + "/DisasterDemo.unity";
            EditorSceneManager.SaveScene(scene, path);
            AssetDatabase.SaveAssets();
            Debug.Log($"Disaster Survival demo scene saved to {path}. Press Play.");
        }

        // ------------------------------------------------------------ helpers

        static GameObject Box(string name, Transform parent, Vector3 position, Vector3 size, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = name;
            go.transform.position = position;
            go.transform.localScale = size;
            // Parent afterwards so the world size stays the same even under a scaled parent
            if (parent != null) go.transform.SetParent(parent, true);
            go.GetComponent<Renderer>().sharedMaterial = mat;
            return go;
        }

        static void Ramp(string name, Transform parent, Vector3 bottom, Vector3 top, float width, Material mat)
        {
            var dir = top - bottom;
            var go = Box(name, parent, (bottom + top) * 0.5f, new Vector3(width, 0.4f, dir.magnitude), mat);
            go.transform.rotation = Quaternion.LookRotation(dir.normalized, Vector3.up);
        }

        static GameObject TriggerZone(string name, Transform parent, Vector3 center, Vector3 size)
        {
            var go = new GameObject(name);
            if (parent != null) go.transform.SetParent(parent, true);
            go.transform.position = center;
            var c = go.AddComponent<BoxCollider>();
            c.isTrigger = true;
            c.size = size;
            return go;
        }

        static GameObject Capsule(string name, Vector3 position, Material mat)
        {
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = name;
            go.transform.position = position;
            go.GetComponent<Renderer>().sharedMaterial = mat;
            Object.DestroyImmediate(go.GetComponent<CapsuleCollider>());
            var cc = go.AddComponent<CharacterController>();
            cc.height = 2f; cc.radius = 0.45f; cc.center = Vector3.zero;
            return go;
        }

        static Material Mat(string name, Color color)
        {
            var path = $"{_matFolder}/{name}.mat";
            var existing = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (existing != null) { existing.color = color; return existing; }

            Shader shader = null;
            var pipeline = GraphicsSettings.currentRenderPipeline;
            if (pipeline != null)
            {
                shader = pipeline.defaultMaterial != null ? pipeline.defaultMaterial.shader : null;
                if (shader == null) shader = Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("HDRP/Lit");
            }
            if (shader == null) shader = Shader.Find("Standard");
            var m = new Material(shader) { color = color };
            AssetDatabase.CreateAsset(m, path);
            return m;
        }

        static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            var parent = Path.GetDirectoryName(path).Replace('\\', '/');
            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
