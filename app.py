from flask import Flask, jsonify, render_template

import requests



app = Flask(__name__)



BOC_INFLATION_GROUP_URL = (

    "https://www.bankofcanada.ca/valet/observations/group/ATABLE_INFLATIOON_INDICATORS/json"

)



# Fallback explanations in case the API description field is empty

FALLBACK_DESCRIPTIONS = {

    "CPI_COMMON": (

        "Tracks common price changes across categories, filtering out"

        " idiosyncratic shocks."

    ),

    "CPI_MEDIAN": (

        "The price change corresponding to the 50th percentile of the weighted"

        " CPI distribution."

    ),

    "CPI_TRIM": (

        "Excludes components whose price changes lie in the extreme upper and"

        " lower tails."

    ),

    "STATIC_ATABLE_BL800502": (

        "Measures the percentage change in the total consumer price basket"

        " year-over-year."

    ),

    "STATIC_ATABLE_CPIHL": (

        "Core inflation excluding volatile items such as fruit, gasoline, and"

        " mortgage interest."

    ),

    "STATIC_ATABLE_CPIILL": (

        "Specialized Bank of Canada analytical price index series."

    ),

}





@app.route("/")

def index():

    """Renders the frontend dashboard."""

    return render_template("index.html")





@app.route("/api/inflation", methods=["GET"])

def get_inflation_data():

    """Fetches live inflation data, current values, and detailed explanations."""

    try:

        response = requests.get(BOC_INFLATION_GROUP_URL, timeout=10)

        response.raise_for_status()

        data = response.json()



        series_details = data.get("seriesDetails", {})

        observations = data.get("observations", [])



        if not observations:

            return (

                jsonify(

                    {

                        "success": False,

                        "error": (

                            "Bank of Canada API returned an empty observations"

                            " payload."

                        ),

                    }

                ),

                500,

            )



        formatted_obs = []

        series_keys = set()



        for obs in observations:

            date_val = obs.get("d")

            row = {"date": date_val}



            for key, val in obs.items():

                if key == "d":

                    continue

                series_keys.add(key)

                if isinstance(val, dict) and "v" in val:

                    try:

                        row[key] = float(val["v"])

                    except (ValueError, TypeError):

                        row[key] = None

                else:

                    row[key] = None



            formatted_obs.append(row)



        # Find the latest valid observation for each series dynamically

        latest_values = {}

        for sk in series_keys:

            for obs in reversed(observations):

                val_obj = obs.get(sk)

                if isinstance(val_obj, dict) and val_obj.get("v") is not None:

                    try:

                        latest_values[sk] = {

                            "value": float(val_obj["v"]),

                            "date": obs.get("d"),

                        }

                        break

                    except (ValueError, TypeError):

                        continue



        # Build metadata with live values and detailed explanations

        metadata = {}

        for sk in series_keys:

            details = series_details.get(sk, {})

            api_label = details.get("label")

            api_desc = details.get("description")

            fallback_desc = FALLBACK_DESCRIPTIONS.get(

                sk, "Official Bank of Canada inflation indicator."

            )



            base_desc = (

                api_desc if api_desc and api_desc.strip() else fallback_desc

            )

            label = (

                api_label

                if api_label and api_label != sk

                else sk.replace("_", " ")

            )

            unit = details.get("unit", "%")



            latest_info = latest_values.get(sk, {"value": None, "date": None})

            val_str = (

                f"{latest_info['value']}{unit}"

                if latest_info["value"] is not None

                else "N/A"

            )

            date_str = (

                f" (As of {latest_info['date']})"

                if latest_info["date"]

                else ""

            )



            # Combine live current value and detailed explanation for the card view

            detailed_explanation = (

                f"Current Value: {val_str}{date_str}\n\n{base_desc}"

            )



            metadata[sk] = {

                "label": label,

                "description": detailed_explanation,

                "unit": unit,

                "latest_value": latest_info["value"],

                "latest_date": latest_info["date"],

            }



        # Calculate Yearly Averages (grouped by Year extracted from observation dates)

        yearly_aggregation = {}

        for obs in formatted_obs:

            date_str = obs.get("date")

            if not date_str or len(date_str) < 4:

                continue

            year = date_str[:4]



            if year not in yearly_aggregation:

                yearly_aggregation[year] = {

                    sk: {"sum": 0.0, "count": 0} for sk in series_keys

                }



            for sk in series_keys:

                val = obs.get(sk)

                if val is not None:

                    yearly_aggregation[year][sk]["sum"] += val

                    yearly_aggregation[year][sk]["count"] += 1



        yearly_data = []

        for year in sorted(yearly_aggregation.keys()):

            row = {"date": year}

            for sk in series_keys:

                stats = yearly_aggregation[year][sk]

                if stats["count"] > 0:

                    row[sk] = round(stats["sum"] / stats["count"], 2)

                else:

                    row[sk] = None

            yearly_data.append(row)



        return jsonify(

            {

                "success": True,

                "metadata": metadata,

                "data": formatted_obs,

                "yearly_data": yearly_data,

            }

        )



    except requests.exceptions.RequestException as e:

        return (

            jsonify(

                {

                    "success": False,

                    "error": (

                        "Failed to connect to Bank of Canada API:"

                        f" {str(e)}"

                    ),

                }

            ),

            500,

        )





if __name__ == "__main__":

    app.run(debug=True, port=8080)