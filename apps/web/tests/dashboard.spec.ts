import { expect, test } from "@playwright/test";

async function createProject(page: import("@playwright/test").Page, name: string) {
  await page.goto("/");
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create project" }).click();
  await expect(page.getByRole("button", { name: new RegExp(name) })).toBeVisible();
}

async function createPromptWithVersion(page: import("@playwright/test").Page, promptName: string, systemPrompt: string) {
  await page.getByLabel("Prompt name").fill(promptName);
  await page.getByRole("button", { name: "Create prompt" }).click();
  await page.getByRole("button", { name: new RegExp(promptName) }).click();
  await page.getByLabel("System prompt").fill(systemPrompt);
  await page.getByLabel("User template").fill("{{message}}");
  await page.getByRole("button", { name: "Create version" }).click();
  await expect(page.getByText("Version 1").last()).toBeVisible();
}

async function createAdditionalPromptVersion(page: import("@playwright/test").Page, systemPrompt: string, userTemplate: string) {
  await page.getByLabel("System prompt").fill(systemPrompt);
  await page.getByLabel("User template").fill(userTemplate);
  await page.getByRole("button", { name: "Create version" }).click();
}

async function createDatasetWithCase(page: import("@playwright/test").Page, datasetName: string) {
  await page.getByRole("button", { name: "Datasets" }).click();
  await page.getByLabel("Dataset name").fill(datasetName);
  await page.getByRole("button", { name: "Create dataset" }).click();
  await page.getByRole("button", { name: new RegExp(datasetName) }).click();
  await page.getByLabel("Case name").fill("monthly refund");
  await page.getByLabel("Input JSON").fill('{"message":"Refund my monthly subscription"}');
  await page.getByLabel("Expected output JSON").fill('{"tool":{"name":"refund_customer"}}');
  await page.getByRole("button", { name: "Add case" }).click();
  await expect(page.getByText("monthly refund")).toBeVisible();
}

async function createCompletedExperiment(page: import("@playwright/test").Page, name: string) {
  await createProject(page, `${name} project`);
  await createPromptWithVersion(page, "baseline", "You are a support agent. Escalate enterprise refunds.");
  await createPromptWithVersion(page, "candidate", "You are a support agent. Refund monthly plans directly.");
  await createDatasetWithCase(page, "refunds");

  await page.getByRole("button", { name: "Experiments" }).click();
  await page.getByLabel("Experiment name").fill(name);
  await page.getByLabel("Baseline prompt").selectOption({ label: "baseline" });
  await page.getByLabel("Candidate prompt").selectOption({ label: "candidate" });
  await page.getByLabel("Provider").selectOption("mock");
  await page.getByRole("button", { name: "Run experiment" }).click();

  await expect(page.getByRole("button", { name: new RegExp(name) })).toBeVisible();
  await expect(page.getByText("Verdict")).toBeVisible();
  await expect(page.getByRole("definition").filter({ hasText: /PASS|FAIL|ERROR|CANCELLED|Pending/ }).first()).toBeVisible();
}

test("runs the local PromptDiff workflow end to end", async ({ page }) => {
  await createCompletedExperiment(page, `e2e-${Date.now()}`);
  await expect(page.getByText("Case detail")).toBeVisible();
  await expect(page.getByRole("button", { name: /case 1/i })).toBeVisible();
  await page.getByRole("button", { name: /case 1/i }).click();
  await expect(page.getByText("Input")).toBeVisible();
  await expect(page.getByText("Baseline output")).toBeVisible();
  await expect(page.getByText("Candidate output")).toBeVisible();
  await expect(page.getByText("Metrics")).toBeVisible();
  await expect(page.getByText("Evaluator results")).toBeVisible();
  await expect(page.getByText("Tool calls")).toBeVisible();
  await expect(page.getByText("Output diff")).toBeVisible();
  await expect(page.getByText("Tool diff")).toBeVisible();
});

test("compares two prompt versions", async ({ page }) => {
  await createProject(page, `prompt-diff-${Date.now()}`);
  await createPromptWithVersion(page, "refund policy", "Escalate enterprise refunds.");
  await expect(page.getByText("Create another version to compare prompt changes.")).toBeVisible();

  await createAdditionalPromptVersion(page, "Refund monthly plans directly.\nEscalate enterprise refunds.", "{{message}}\nReturn JSON.");
  await expect(page.getByText("Prompt diff")).toBeVisible();
  await expect(page.getByLabel("Baseline version")).toBeVisible();
  await expect(page.getByLabel("Candidate version")).toBeVisible();
  await expect(page.locator(".prompt-diff-table").getByText("Escalate enterprise refunds.").first()).toBeVisible();
  await expect(page.locator(".prompt-diff-table").getByText("Refund monthly plans directly.")).toBeVisible();

  await page.getByRole("button", { name: "User template" }).click();
  await expect(page.locator(".prompt-diff-table").getByText("Return JSON.")).toBeVisible();
});

test("blocks invalid dataset case JSON before submit", async ({ page }) => {
  await createProject(page, `invalid-json-${Date.now()}`);
  await createDatasetWithCase(page, "valid-dataset");

  await page.getByLabel("Input JSON").fill("{");
  await page.getByRole("button", { name: "Add case" }).click();

  await expect(page.locator(".alert")).toContainText("Input must be valid JSON.");
  await expect(page.getByText("Untitled case")).toHaveCount(0);
});

test("shows export links for a completed experiment", async ({ page }) => {
  await createCompletedExperiment(page, `export-${Date.now()}`);

  await expect(page.getByRole("link", { name: "json" })).toBeVisible();
  await expect(page.getByRole("link", { name: "markdown" })).toBeVisible();
  await expect(page.getByRole("link", { name: "csv" })).toBeVisible();
  await expect(page.getByRole("link", { name: "junit" })).toBeVisible();
});
