import { useConfigureSuggestions } from "@copilotkit/react-core/v2";

export const useExampleSuggestions = () => {
  useConfigureSuggestions({
    suggestions: [
      {
        title: "Show my name",
        message:
          "Please show my name in the chat.",
      },
      {
        title: "Pie chart",
        message:
          "Please show me the distribution of our revenue by category in a pie chart.",
      },
      {
        title: "Bar chart",
        message:
          "Please compare our revenue by category in a bar chart.",
      },
    ],
    available: "always",
  });
};
