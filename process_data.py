import glob
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point
import osmnx as ox
import warnings

# הסתרת אזהרות ושיפור ביצועי OSM
warnings.filterwarnings('ignore')
ox.settings.log_console = False
ox.settings.use_cache = True

TRIPS_FILE = 'AvgDayHourlyTrips201819_1270_weekday_v1.csv'
ZONES_EXCEL = 'מאפייני אזורי_תנועה_-_ספטמבר_2021.xlsx'
OUTPUT_FILE = 'dots_data.js'

# מילון עוגנים ידני: השתלת קואורדינטות מדויקות ליישובים חסרים/בעייתיים בסוף הריצה
MANUAL_OVERRIDES = {
    "נווה גנים (ליד משכנות אומנים)": (32.855026, 35.090925),
    "כפר ביאליק": (32.820200, 35.086476),
    "מנוף": (32.854035, 35.236859),
    "שכניה": (32.848988, 35.246944),
    "קורנית": (32.843688, 35.252094),
    "מורשת": (32.825761, 35.231850),
    "יודפת": (32.837708, 35.273567),
    "הררית": (32.845482, 35.368254),
    "לוטם": (32.882172, 35.357547),
    "עדי": (32.782274, 35.172559),
    "הרדוף": (32.763801, 35.172878),
    "אלון הגליל": (32.756818, 35.220428),
    "הסוללים": (32.751158, 35.237850),
    "חנתון": (32.783713, 35.245438),
    "נופית": (32.761481, 35.147820),
    "קעביה": (32.757863, 35.184004),
    "מרכז טבעון": (32.723377, 35.135218),
    "אלונים": (32.720705, 35.144709),
    "אלוני אבא": (32.730147, 35.171449),
    "בית לחם הגלילית": (32.734678, 35.190868),
    "כפר יהושוע": (32.680662, 35.151790),
    "שמשית": (32.732506, 35.248069),
    "ציפורי": (32.746772, 35.277444),
    "הושעיה": (32.758062, 35.294261),
    "זרזיר": (32.726982, 35.215350),
    "בית קשת": (32.718549, 35.394414),
    "כפר תבור": (32.687058, 35.421364),
    "עין דור": (32.656371, 35.416912),
    "כפר קיש": (32.666215, 35.449463),
    "גזית": (32.638748, 35.447225),
    "שרונה": (32.725410, 35.469601),
    "יבניאל": (32.703425, 35.505734),
    "הזורעים": (32.748097, 35.501832),
    "רמת דוד": (32.678717, 35.202664),
    "גבת": (32.676264, 35.213467),
    "שריד": (32.663288, 35.223663),
    "כפר ברוך": (32.646119, 35.191861),
    "גניגר": (32.663288, 35.259714),
    "היוגב": (32.612282, 35.206912),
    "כפר יחזקאל": (32.566790, 35.360517),
    "עין חרוד": (32.555780, 35.394872),
    "בית השיטה": (32.550852, 35.438971),
    "בית אלפא": (32.516884, 35.428702),
    "ניר דוד": (32.504507, 35.457885),
    "שדה נחום": (32.524943, 35.483484),
    "גבע": (32.565991, 35.372358),
    "מגידו": (32.579567, 35.179480),
    "מדרך עוז": (32.595318, 35.158188),
    "משמר העמק": (32.610032, 35.141588),
    "הזורע": (32.644425, 35.119358),
    "רמת השופט": (32.610003, 35.093381),
    "עין השופט": (32.595532, 35.100382),
    "דליה": (32.589999, 35.075770),
    "רמות מנשה": (32.597660, 35.057871),
    "גבעת נילי": (32.548352, 35.041373),
    "עמיקם": (32.564011, 35.020613),
    "אביאל": (32.532313, 34.993886),
    "רגבים": (32.522759, 35.034448),
    "בת שלמה": (32.600430, 35.004131),
    "עופר": (32.622533, 34.982215),
    "כרם מהרל": (32.644068, 34.991360),
    "נווה ים": (32.678336, 34.931654),
    "עין הוד": (32.700163, 34.983551),
    "ימין אורד": (32.701621, 34.988675),
    "בית אורן": (32.731133, 35.005997),
    "אוספיה": (32.720568, 35.059334),
    "זהולוק": (32.708347, 35.076566),
    "קריית אליהו": (32.824188, 34.987350)
}

def main():
    print("1. טוען נתונים ופוליגונים משרד התחבורה...")
    try:
        trips_df = pd.read_csv(TRIPS_FILE)
        zones_df = pd.read_excel(ZONES_EXCEL, sheet_name='1270', header=2)
    except Exception as e:
        print("שגיאה:", e)
        return

    trips_df['morning_trips'] = trips_df['h7'] + trips_df['h8'] + trips_df['h9']
    origin_volumes = trips_df.groupby('fromZone')['morning_trips'].sum().reset_index()
    demand_zones = set(origin_volumes['fromZone'])

    zones_names = zones_df[['אזור 1270', 'שיוך מוניצפלי', 'פירוט אזור']].copy()
    demand_df = pd.merge(origin_volumes, zones_names, left_on='fromZone', right_on='אזור 1270', how='inner')

    shp_files = glob.glob('**/*.shp', recursive=True)
    best_shp, best_col, max_overlap = None, None, 0
    for shp_path in shp_files:
        try:
            gdf = gpd.read_file(shp_path)
            for col in gdf.columns:
                try:
                    numeric_col = pd.to_numeric(gdf[col], errors='coerce')
                    overlap = len(set(numeric_col.dropna()).intersection(demand_zones))
                    if overlap > max_overlap:
                        max_overlap, best_col, best_shp = overlap, col, shp_path
                except: pass
        except: pass

    gdf = gpd.read_file(best_shp)
    if gdf.crs is None: gdf.set_crs(epsg=2039, inplace=True)
    if gdf.crs.to_epsg() != 4326: gdf = gdf.to_crs(epsg=4326)

    gdf[best_col] = pd.to_numeric(gdf[best_col], errors='coerce')
    merged_gdf = pd.merge(gdf, demand_df, left_on=best_col, right_on='fromZone', how='inner')

    merged_gdf['cen_lat'] = merged_gdf.geometry.centroid.y
    merged_gdf['cen_lon'] = merged_gdf.geometry.centroid.x
    filtered_gdf = merged_gdf[
        (merged_gdf['morning_trips'] > 20) & 
        (merged_gdf['cen_lat'] > 32.5) & (merged_gdf['cen_lat'] < 33.2) & 
        (merged_gdf['cen_lon'] > 34.8) & (merged_gdf['cen_lon'] < 35.6)
    ]

    print("2. שואב נתוני אזורי מגורים מ-OpenStreetMap (נא להמתין, לוקח זמן)...")
    try:
        merged_geom = filtered_gdf.unary_union
        tags = {'landuse': 'residential'}
        osm_data = ox.features_from_polygon(merged_geom, tags=tags)
        osm_union = osm_data.unary_union
        print(" -> נתוני הרחובות הבנויים ירדו בהצלחה!")
    except Exception as e:
        print(" -> שגיאה מול OSM (ייתכן ניתוק), נחזור לגיבוי גיאומטרי:", e)
        osm_union = None

    print("3. קולע את האוכלוסייה לתוך שטחי המגורים (OSM Masking)...")
    js_content = "const simulatedPeople = [\n"
    count_dots = 0
    density_multiplier = 2.5 

    # --- שלב א': פיזור רגיל לפי פוליגונים (קוד גרסה 7 המקורי) ---
    for index, row in filtered_gdf.iterrows():
        geom = row['geometry']
        pop = int(row['morning_trips'])
        
        muni = str(row['שיוך מוניצפלי']).replace("'", "").replace('"', '').strip()
        detail = str(row['פירוט אזור']).replace("'", "").replace('"', '').strip()
        name = f"{muni} - {detail}" if detail and detail != 'nan' else muni

        base_dots = (pop ** 0.5) * density_multiplier
        num_dots = max(10, int(round(base_dots)))

        target_geom = geom
        if osm_union is not None:
            intersected = geom.intersection(osm_union)
            if not intersected.is_empty and intersected.area > 0.000001:
                target_geom = intersected

        minx, miny, maxx, maxy = target_geom.bounds
        points_found = 0
        attempts = 0
        max_attempts = num_dots * 1000 

        while points_found < num_dots and attempts < max_attempts:
            attempts += 1
            pnt = Point(np.random.uniform(minx, maxx), np.random.uniform(miny, maxy))
            if target_geom.contains(pnt):
                js_content += f"    {{ lat: {pnt.y:.5f}, lon: {pnt.x:.5f}, name: '{name}', pop: {pop} }},\n"
                points_found += 1
                count_dots += 1
                
        while points_found < num_dots:
            pnt = Point(np.random.uniform(geom.bounds[0], geom.bounds[2]), np.random.uniform(geom.bounds[1], geom.bounds[3]))
            if geom.contains(pnt):
                js_content += f"    {{ lat: {pnt.y:.5f}, lon: {pnt.x:.5f}, name: '{name}', pop: {pop} }},\n"
                points_found += 1
                count_dots += 1

    # --- שלב ב': הפלסטר הכירורגי שלך (השלמת הנקודות החסרות) ---
    print("4. מורח 'פלסטר': מוסיף נקודות באופן נקודתי מהרשימה הידנית...")
    for loc_name, (pt_lat, pt_lon) in MANUAL_OVERRIDES.items():
        # נייצר 12 נקודות (עם pop סטנדרטי) לכל יישוב חסר כדי שיופיע בצורה מובהקת במפה
        for _ in range(12):
            rnd_lon = np.random.normal(pt_lon, 0.0015)
            rnd_lat = np.random.normal(pt_lat, 0.0015)
            js_content += f"    {{ lat: {rnd_lat:.5f}, lon: {rnd_lon:.5f}, name: '{loc_name}', pop: 25 }},\n"
            count_dots += 1

    js_content += "];\n"
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(js_content)
        
    print(f"סיימנו! {count_dots} נקודות נוצרו בהצלחה (כולל ההשלמות הידניות).")

if __name__ == "__main__":
    main()