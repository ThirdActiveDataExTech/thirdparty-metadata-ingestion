/** 진입점 — 화면을 등록하고 띄운다.
 *
 * core는 화면을 import하지 않는다. 하면 core ↔ 화면이 서로를 불러 순환이 된다.
 * 등록을 여기서 하면 core는 화면을 모른 채 라우팅만 한다.
 */
import {$, register, drawNav, render} from "./core.js";
import {viewOps} from "./ops.js";
import {viewFind, runSearch} from "./find.js";
import {viewDetail} from "./detail.js";
import {viewGraph} from "./graph.js";
import {viewBundle} from "./bundle.js";
import {viewReview} from "./review.js";
import {viewLabel} from "./label.js";
import {viewStruct} from "./struct.js";

register("ops", viewOps);
register("find", viewFind);
register("detail", viewDetail);
register("graph", viewGraph);
register("bundle", viewBundle);
register("review", viewReview);
register("label", viewLabel);
register("struct", viewStruct);

$("#qf").onsubmit = e => { e.preventDefault(); runSearch(); };
drawNav();
render();
