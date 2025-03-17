import pandas as pd
import streamlit as st
from datetime import datetime
import altair as alt

# Show the page title and description.
st.set_page_config(page_title="Gambolgold")
st.title("Gambolgold")
st.write(
    """
    This app visualizes data from [Barchart](https://www.barchart.com/options/condor-strategies/long-iron-condor?orderBy=baseSymbol&orderDir=asc&screener=313707&viewName=main&page=4).
    """
)

# Function to load data from a CSV. We're caching this so it doesn't reload every time the app
# reruns (e.g. if the user interacts with the widgets).
@st.cache_data
def load_data(uploaded_file):
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        return df
    else:
        st.error("No file uploaded.")
        return None

# File uploader widget
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# Load the data only if a file is uploaded
if uploaded_file is not None:
    # Load the data (cached until button press)
    df = load_data(uploaded_file)
    
    # Show the button to refresh the data
    if st.button("Refresh Data"):
        # Clear the cache for the load_data function to reload the data
        st.cache_data.clear()  # Clears the cache of load_data()

        # Reload the data from the CSV after clearing cache
        df = load_data(uploaded_file)
        st.success("Data refreshed!")
    
    ########################################
    # Data Cleaning
    df['Row Index'] = df.index
    df.drop(df.index[-1], axis=0, inplace=True)

    def convert_Profit_Prob_to_float(percent_str):
        return float(percent_str.replace('%', ''))
    df['Profit Prob'] = df['Profit Prob'].apply(convert_Profit_Prob_to_float)

    def convert_Risk_Reward_to_float(percent_str):
        return float(percent_str.replace(' to 1', ''))
    df['Risk/Reward'] = round(100/df['Risk/Reward'].apply(convert_Risk_Reward_to_float), 1)

    def days_between(future_date):
        today = datetime.today()
        date_difference = future_date - today
        return date_difference.days
    for index, row in df.iterrows():
        future_date = datetime.strptime(row['Exp Date'], "%m/%d/%Y")
        df.at[index, 'Duration'] = days_between(future_date) + 1

    ########################################
    # Rename Columns
    df.rename(columns={'Price~':'Market Price', 'Risk/Reward':'Profitability'}, inplace=True)

    ########################################
    # Grade Calculation
    def grade_profitability(prof):
        profitability_ranges = [60, 70, 80, 90, 100, 125, 150, 200, 300]
        profitability_grade = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        for count in range(len(profitability_ranges)):
            if prof < profitability_ranges[count]:
                return profitability_grade[count]
            elif prof >= profitability_ranges[-1]:
                return 1

    def grade_profit_prob(profit_prob):
        profit_prob_ranges = [30, 35, 40, 45, 50, 55, 60]
        profit_prob_grade = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        for count in range(len(profit_prob_ranges)):
            if profit_prob < profit_prob_ranges[count]:
                return profit_prob_grade[count]
            elif profit_prob >= profit_prob_ranges[-1]:
                return 1

    grade_weight = {
        'w_profit_probability' : 50,
        'w_profitability' : 50,
        'w_duration' : 0,
        'w_time_until_event' : 0 
    }

    for index, row in df.iterrows():
        prof = row['Profitability']
        profitability_grade = grade_profitability(prof)
        profit_prob = row['Profit Prob']
        profit_prob_grade = grade_profit_prob(profit_prob)

        profitability_part = profitability_grade * grade_weight['w_profitability']
        profit_prob_part = profit_prob_grade * grade_weight['w_profit_probability']
        duration_part = (10/row['Duration']) * grade_weight['w_duration']

        df.at[index, 'Grade'] = round(profit_prob_part + profitability_part + duration_part, 1)

    # Profitability and Profit Probability slider
    profitability = st.slider("Profitability", 0, 100, step=1, value=50)
    profit_prob = st.slider("Profit Probability", 0, 100, step=1, value=50)

    # Filter data based on user selection
    df_filtered = df[(df["Profitability"]>=profitability) & (df["Profit Prob"]>=profit_prob)]

    # Check if the filtered data is empty
    if df_filtered.empty:
        st.warning("No data points in this range.")
    else:
        # Dynamic x and y axis selection based on slider values
        x_axis = 'Profit Prob'  # This could be dynamic if you want, e.g., by another slider
        y_axis = 'Profitability'  # Same here

        # Add padding to the plot to prevent edge points from being cut off
        buffer_x = 0.05 * (df_filtered[x_axis].max() - df_filtered[x_axis].min())
        buffer_y = 0.05 * (df_filtered[y_axis].max() - df_filtered[y_axis].min())

        # Scatter plot with dynamic axes and added padding
        click = alt.selection_point(fields=['Row Index'], nearest=True, on='click', empty=True)

        scatter = alt.Chart(df_filtered).mark_circle(size=100).encode(
            x=alt.X(
                x_axis,
                title=f'{x_axis}',
                scale=alt.Scale(
                    domain=[
                        df_filtered[x_axis].min() - buffer_x,
                        df_filtered[x_axis].max() + buffer_x
                    ]
                )
            ),
            y=alt.Y(
                y_axis,
                title=f'{y_axis}',
                scale=alt.Scale(
                    domain=[
                        df_filtered[y_axis].min() - buffer_y,
                        df_filtered[y_axis].max() + buffer_y
                    ]
                )
            ),
            color=alt.Color('Duration', legend=alt.Legend(title='Duration')),
            opacity=alt.condition(click, alt.value(1), alt.value(0.3)),
            tooltip=['Row Index', 'Symbol', 'Profit Prob', 'Profitability', 'Duration']
        ).add_params(
            click
        ).properties(
            title=f"{y_axis} vs {x_axis} for Different Durations"
        ).interactive()

        # Display chart in Streamlit
        st.altair_chart(scatter, use_container_width=True, on_select="rerun")

        # Display filtered data
        # Data selection widget
        data_selected = st.multiselect(
            "Data",
            list(df.columns),
            ['Row Index', 'Symbol', 'Grade', 'Profitability', 'Profit Prob', 'Duration']
        )
        df_selected_filtered = df_filtered[data_selected]
       
        st.dataframe(df_selected_filtered, use_container_width=True)

else:
    st.warning("Please upload a CSV file to proceed.")