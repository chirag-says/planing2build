// Concept floor plan types, taken only from the generated API contract (IC 7.7). The HousePlan
// document is the source of truth; PlanGeometry is the server's derived drawing input (HR O.2).
import type { components } from "@p2b/contracts";

type Schemas = components["schemas"];

export type PlanDetail = Schemas["HousePlanDetailOut"];
export type EditedPlan = Schemas["EditHousePlanOut"];
export type HousePlan = Schemas["HousePlan"];
export type PlanGeometry = Schemas["PlanGeometry"];
export type FloorGeometry = Schemas["FloorGeometry"];
export type RoomGeom = Schemas["RoomGeom"];
export type WallGeom = Schemas["WallGeom"];
export type OpeningGeom = Schemas["OpeningGeom"];
export type FixtureGeom = Schemas["FixtureGeom"];
export type OpenArea = Schemas["OpenArea"];
export type DimensionChain = Schemas["DimensionChain"];
export type GPoint = Schemas["GPoint"];
export type ValidationReport = Schemas["ValidationReport"];
export type ValidationIssue = Schemas["ValidationIssue"];
export type EditingInfo = Schemas["EditingOut"];
export type PlanOp = Schemas["EditHousePlanRequest"]["ops"][number];
export type MoveWallOp = Schemas["MoveWall"];
export type MoveOpeningOp = Schemas["MoveOpening"];
export type Opening = Schemas["Opening"];
export type Compromise = Schemas["Compromise"];
export type RoomType = Schemas["RoomType"];
export type RoomSideName = Schemas["RoomSide"];
export type PlanVersion = Schemas["HousePlanVersionOut"];
export type PlanRevision = Schemas["HousePlanRevisionOut"];
export type InsertionSlot = Schemas["InsertionSlotOut"];
export type AssistantEdit = Schemas["AssistantEditOut"];

/** The part of a plan detail the drawing and the editor read. */
export interface PlanState {
  document: HousePlan;
  geometry: PlanGeometry;
  validation: ValidationReport | null;
  editing: EditingInfo;
}
