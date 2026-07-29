#!/usr/bin/env python3
"""Generate a realistic MuleSoft application with five planted defects.

The generated files contain NO comments marking the defects. An earlier version
annotated each flaw in the XML, which made the demo worthless: the room would
watch a model "discover" problems that were labelled in the source.

The defects sit inside code that otherwise looks like a competent integration.
Several things are done correctly on purpose, because a reviewer finding a
hardcoded password in a file where every other value comes from a properties
file is a far better demo than one where nothing is externalised.

    python3 seed_flaws.py --dest ../order-api
    python3 seed_flaws.py --list        # what gets planted, for your notes
"""
import argparse
import pathlib
import sys

FILES = {}

# --------------------------------------------------------------------------
# Global configuration. Most values come from the properties file. One does
# not, and that inconsistency is the whole point.
# --------------------------------------------------------------------------
FILES["src/main/mule/global-config.xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db"
      xmlns:tls="http://www.mulesoft.org/schema/mule/tls"
      xmlns:secure-properties="http://www.mulesoft.org/schema/mule/secure-properties"
      xmlns:doc="http://www.mulesoft.org/schema/mule/documentation"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd
        http://www.mulesoft.org/schema/mule/db
        http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd
        http://www.mulesoft.org/schema/mule/tls
        http://www.mulesoft.org/schema/mule/tls/current/mule-tls.xsd
        http://www.mulesoft.org/schema/mule/secure-properties
        http://www.mulesoft.org/schema/mule/secure-properties/current/mule-secure-properties.xsd">

  <configuration-properties file="config/${mule.env}.yaml" doc:name="Environment properties"/>

  <secure-properties:config name="secureProps"
                            file="config/${mule.env}-secure.yaml"
                            key="${encryption.key}">
    <secure-properties:encrypt algorithm="AES" mode="CBC"/>
  </secure-properties:config>

  <http:listener-config name="ordersHttpListener" doc:name="Orders inbound">
    <http:listener-connection host="0.0.0.0" port="${http.port}" protocol="HTTP"/>
  </http:listener-config>

  <http:request-config name="fulfilmentApi" doc:name="Fulfilment downstream">
    <http:request-connection host="${fulfilment.host}"
                             port="${fulfilment.port}"
                             protocol="HTTPS">
      <tls:context>
        <tls:trust-store path="truststore.jks"
                         password="${secure::truststore.password}"
                         type="jks"/>
      </tls:context>
    </http:request-connection>
  </http:request-config>

  <db:config name="ordersDb" doc:name="Orders database">
    <db:my-sql-connection host="${orders.db.host}"
                          port="${orders.db.port}"
                          user="${orders.db.user}"
                          password="Wint3r2026!"
                          database="${orders.db.name}"/>
  </db:config>

</mule>
'''

# --------------------------------------------------------------------------
# Flows. Two of the three have proper error handling. The third does not.
# --------------------------------------------------------------------------
FILES["src/main/mule/order-api.xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db"
      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"
      xmlns:apikit="http://www.mulesoft.org/schema/mule/mule-apikit"
      xmlns:doc="http://www.mulesoft.org/schema/mule/documentation"
      xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
      xsi:schemaLocation="
        http://www.mulesoft.org/schema/mule/core
        http://www.mulesoft.org/schema/mule/core/current/mule.xsd
        http://www.mulesoft.org/schema/mule/http
        http://www.mulesoft.org/schema/mule/http/current/mule-http.xsd
        http://www.mulesoft.org/schema/mule/db
        http://www.mulesoft.org/schema/mule/db/current/mule-db.xsd
        http://www.mulesoft.org/schema/mule/ee/core
        http://www.mulesoft.org/schema/mule/ee/core/current/mule-ee.xsd
        http://www.mulesoft.org/schema/mule/mule-apikit
        http://www.mulesoft.org/schema/mule/mule-apikit/current/mule-apikit.xsd">

  <apikit:config name="orderApiConfig"
                 raml="api/order-api.raml"
                 outboundHeadersMapName="outboundHeaders"
                 httpStatusVarName="httpStatus"/>

  <flow name="order-api-main" doc:name="API listener">
    <http:listener config-ref="ordersHttpListener" path="/api/*">
      <http:response statusCode="#[vars.httpStatus default 200]">
        <http:headers>#[vars.outboundHeaders default {}]</http:headers>
      </http:response>
    </http:listener>
    <apikit:router config-ref="orderApiConfig" doc:name="APIkit router"/>
    <error-handler ref="globalErrorHandler"/>
  </flow>

  <flow name="getOrderFlow" doc:name="GET /orders/{orderId}">
    <db:select config-ref="ordersDb" doc:name="Select order">
      <db:sql><![CDATA[
        SELECT o.id, o.status, o.placed_at, o.total_amount, o.currency
        FROM orders o
        WHERE o.id = :orderId
      ]]></db:sql>
      <db:input-parameters><![CDATA[#[{ orderId: attributes.uriParams.orderId }]]]></db:input-parameters>
    </db:select>

    <choice doc:name="Found?">
      <when expression="#[isEmpty(payload)]">
        <ee:transform doc:name="404 body">
          <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
  error: "NOT_FOUND",
  message: "No order with id " ++ (attributes.uriParams.orderId default "")
}]]></ee:set-payload>
          </ee:message>
          <ee:variables>
            <ee:set-variable variableName="httpStatus">404</ee:set-variable>
          </ee:variables>
        </ee:transform>
      </when>
      <otherwise>
        <ee:transform doc:name="Order response">
          <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{
  orderId: payload[0].id,
  status: payload[0].status,
  placedAt: payload[0].placed_at as String {format: "yyyy-MM-dd'T'HH:mm:ss'Z'"},
  total: {
    amount: payload[0].total_amount,
    currency: payload[0].currency
  }
}]]></ee:set-payload>
          </ee:message>
        </ee:transform>
      </otherwise>
    </choice>
  </flow>

  <flow name="createCustomerFlow" doc:name="POST /customers">
    <logger level="INFO"
            message="#[payload]"
            doc:name="Log inbound customer"/>

    <ee:transform doc:name="Map to persistence model">
      <ee:message>
        <ee:set-payload><![CDATA[%dw 2.0
output application/java
---
{
  externalRef: payload.customerReference,
  givenName: payload.name.given,
  familyName: payload.name.family,
  email: payload.contact.email,
  phone: payload.contact.phone default null,
  dateOfBirth: payload.dateOfBirth as Date {format: "yyyy-MM-dd"},
  taxFileNumber: payload.taxFileNumber default null
}]]></ee:set-payload>
      </ee:message>
    </ee:transform>

    <db:insert config-ref="ordersDb" doc:name="Insert customer">
      <db:sql><![CDATA[
        INSERT INTO customers (external_ref, given_name, family_name, email, phone, date_of_birth, tfn)
        VALUES (:externalRef, :givenName, :familyName, :email, :phone, :dateOfBirth, :taxFileNumber)
      ]]></db:sql>
      <db:input-parameters><![CDATA[#[payload]]]></db:input-parameters>
    </db:insert>

    <ee:transform doc:name="201 body">
      <ee:message>
        <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ customerId: payload.generatedKeys[0], created: true }]]></ee:set-payload>
      </ee:message>
      <ee:variables>
        <ee:set-variable variableName="httpStatus">201</ee:set-variable>
      </ee:variables>
    </ee:transform>

    <error-handler>
      <on-error-propagate type="DB:QUERY_EXECUTION" doc:name="Duplicate or constraint">
        <ee:transform doc:name="409 body">
          <ee:message>
            <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ error: "CONFLICT", message: "Customer already exists" }]]></ee:set-payload>
          </ee:message>
          <ee:variables>
            <ee:set-variable variableName="httpStatus">409</ee:set-variable>
          </ee:variables>
        </ee:transform>
      </on-error-propagate>
    </error-handler>
  </flow>

  <error-handler name="globalErrorHandler">
    <on-error-propagate type="APIKIT:BAD_REQUEST">
      <ee:transform>
        <ee:message>
          <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ error: "BAD_REQUEST", message: error.description }]]></ee:set-payload>
        </ee:message>
        <ee:variables>
          <ee:set-variable variableName="httpStatus">400</ee:set-variable>
        </ee:variables>
      </ee:transform>
    </on-error-propagate>
    <on-error-propagate type="ANY">
      <logger level="ERROR" message="#['Unhandled: ' ++ error.description]"/>
      <ee:transform>
        <ee:message>
          <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
{ error: "INTERNAL", message: "Unexpected error" }]]></ee:set-payload>
        </ee:message>
        <ee:variables>
          <ee:set-variable variableName="httpStatus">500</ee:set-variable>
        </ee:variables>
      </ee:transform>
    </on-error-propagate>
  </error-handler>

</mule>
'''

# --------------------------------------------------------------------------
# Properties. Everything externalised properly, which makes the one hardcoded
# credential in global-config.xml stand out as an inconsistency.
# --------------------------------------------------------------------------
FILES["src/main/resources/config/dev.yaml"] = '''http:
  port: "8081"

orders:
  db:
    host: "orders-db.dev.internal"
    port: "3306"
    user: "svc_orders"
    name: "orders"

fulfilment:
  host: "fulfilment.dev.internal"
  port: "443"

logging:
  level: "INFO"
'''

FILES["src/main/resources/api/order-api.raml"] = '''#%RAML 1.0
title: Order API
version: v1
mediaType: application/json

/orders:
  /{orderId}:
    get:
      description: Retrieve a single order
      responses:
        200:
        404:

/customers:
  post:
    description: Create a customer record
    body:
      type: object
    responses:
      201:
      409:
'''

FILES["pom.xml"] = '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <groupId>au.com.example.integration</groupId>
  <artifactId>order-api</artifactId>
  <version>1.4.0</version>
  <packaging>mule-application</packaging>
  <name>Order API</name>

  <properties>
    <app.runtime>4.6.0</app.runtime>
    <mule.maven.plugin.version>4.1.1</mule.maven.plugin.version>
    <munit.version>3.1.0</munit.version>
  </properties>

  <build>
    <plugins>
      <plugin>
        <groupId>org.mule.tools.maven</groupId>
        <artifactId>mule-maven-plugin</artifactId>
        <version>${mule.maven.plugin.version}</version>
        <extensions>true</extensions>
      </plugin>
      <plugin>
        <groupId>com.mulesoft.munit.tools</groupId>
        <artifactId>munit-maven-plugin</artifactId>
        <version>${munit.version}</version>
        <executions>
          <execution>
            <id>test</id>
            <phase>test</phase>
            <goals><goal>test</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>

  <dependencies>
    <dependency>
      <groupId>org.mule.connectors</groupId>
      <artifactId>mule-http-connector</artifactId>
      <version>1.9.3</version>
      <classifier>mule-plugin</classifier>
    </dependency>
    <dependency>
      <groupId>org.mule.connectors</groupId>
      <artifactId>mule-db-connector</artifactId>
      <version>1.14.9</version>
      <classifier>mule-plugin</classifier>
    </dependency>
    <dependency>
      <groupId>org.mule.modules</groupId>
      <artifactId>mule-apikit-module</artifactId>
      <version>1.11.2</version>
      <classifier>mule-plugin</classifier>
    </dependency>
    <dependency>
      <groupId>au.com.example.integration</groupId>
      <artifactId>common-transforms</artifactId>
      <version>2.1.0-SNAPSHOT</version>
      <classifier>mule-plugin</classifier>
    </dependency>
  </dependencies>

</project>
'''

PLANTED = [
    ("1", "blocker", "SECRETS",
     "global-config.xml: ordersDb password is a literal, while every other",
     "value in the same config comes from properties"),
    ("2", "blocker", "TRANSPORT",
     "global-config.xml: ordersHttpListener is protocol=HTTP with no TLS,",
     "while the downstream request config correctly uses HTTPS"),
    ("3", "major", "ERROR HANDLING",
     "order-api.xml: getOrderFlow has no error-handler, while the main flow",
     "and createCustomerFlow both do"),
    ("4", "blocker", "DATA PROTECTION",
     "order-api.xml: createCustomerFlow logs #[payload] at INFO before the",
     "transform. That payload carries email, phone, DOB and a tax file number"),
    ("5", "major", "DEPENDENCIES",
     "pom.xml: common-transforms 2.1.0-SNAPSHOT inside a released 1.4.0",
     "artifact"),
]


def print_planted():
    print("\nFive defects planted. None of them are commented in the source:\n")
    for n, sev, rule, line1, line2 in PLANTED:
        print(f"  {n}  {sev:<8} {rule}")
        print(f"     {line1}")
        print(f"     {line2}\n")


def main():
    ap = argparse.ArgumentParser(
        description="Generate a MuleSoft app with five planted defects.")
    ap.add_argument("--dest", default=".", help="target directory (default: cwd)")
    ap.add_argument("--force", action="store_true",
                    help="overwrite existing files instead of refusing")
    ap.add_argument("--list", action="store_true",
                    help="print the planted defects and exit, writing nothing")
    a = ap.parse_args()

    if a.list:
        print_planted()
        return 0

    dest = pathlib.Path(a.dest)
    existing = [f for f in FILES if (dest / f).exists()]
    if existing and not a.force:
        print("refusing to overwrite: " + ", ".join(existing))
        print("re-run with --force, or point --dest somewhere else")
        return 2

    for path, content in FILES.items():
        p = dest / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        print(f"  wrote {p}")

    print_planted()
    print("Next:")
    print("  git checkout -b demo/ai-review")
    print('  git add -A && git commit -m "add order api"')
    print("  git push -u origin demo/ai-review     then open the PR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
