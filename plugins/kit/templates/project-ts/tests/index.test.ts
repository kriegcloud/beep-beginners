import { hello } from "../src/index";

test("hello", () => {
  expect(hello().endsWith("is set up.")).toBe(true);
});
