# Google sheets to ical feed

This app will read event records out of Google sheets and create an ical feed.

## Setup

1. Clone this project! Duh! You'll want your own copy of this code.
1. Set up a Service Account for Google sheet.

   You can find more information at https://developers.google.com/android/management/service-account

   Go to https://console.developers.google.com/projectselector2/apis/credentials and create/select a project.

   Click `Create Credentials` and select `Service Account`. Give your Service Account a name, ID and description. Next, click `Create Key`, select JSON, and downlaod your credentials.

   Share your Google sheet with your Service Account ID. Your Service Account ID will be in the form your-service-account@your-project.iam.gserviceaccount.com
1. Copy the `config.yaml.example` to `config.yaml`.

   Set `authJSONFile` to the Service Account credentials JSON file you downloaded in the previous step.

   Set the `spreadsheetID` to your Google sheet ID and the `sheetName` to the sheet name.

   Set the `startRow`. If you have a header row, set this to 2 (or higher if you have multiple header rows). Otherwise, set this to 1.

   Set your columns. Each column definition should include a `column` (letter), `name` (arbitrary text), and (if required) a `required` attribute.

   Set the `endpoint`. Once you deploy the app, your ical feed will be available at `your-domain/cal/<endpoint>`.

   Set the ical fields. You *must* include the `dtstart`, `dtend`, and `summary` fields. Values may include placeholders (enclosed in square brackets) for the columns you previously defined.
1. Commit your credentials and configs.
1. Add your Heroku remote: `heroku git:remote -a your-heroku-app`.
1. Deploy!
