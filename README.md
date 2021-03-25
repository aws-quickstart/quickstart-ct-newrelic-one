[![New Relic Experimental header](https://github.com/newrelic/opensource-website/raw/master/src/images/categories/Experimental.png)](https://opensource.newrelic.com/oss-category/#new-relic-experimental)

# AWS Control Tower Customization for Integration with New Relic

> This solution helps you automate setup of [New Relic's AWS integration](https://newrelic.com/aws) in your [AWS Control Tower](https://aws.amazon.com/controltower/) managed multi-account environment (landing zone). Once the solution is deployed to your [AWS Control Tower management account](https://docs.aws.amazon.com/controltower/latest/userguide/how-control-tower-works.html#what-is-master), any new accounts you enroll in your landing zone are automatically integrated with New Relic.

## Installation

> The repo includes a couple of [AWS CloudFormation](https://aws.amazon.com/cloudformation/) templates that you are free to download or directly reference their public GitHub URL when trying to create CloudFormation stacks using them, as described in [Usage](#Usage)

## Prerequisites
> Fully deployed AWS Control Tower is required for this solution. You will need administrator privileges in the AWS Control Tower management account to deploy the solution. For information about setting up an AWS Control Tower landing zone, see [Getting Started with AWS Control Tower](https://docs.aws.amazon.com/controltower/latest/userguide/getting-started-with-control-tower.html) in the AWS Control Tower User Guide.

> You are required to have an active New Relic account with Standard or higher pricing tier subscription, when using the new [New Relic One pricing plan](https://docs.newrelic.com/docs/accounts/accounts-billing/new-relic-one-pricing-users/pricing-billing). Don’t have an account yet? [Sign up](https://aws.amazon.com/marketplace/pp/B08L5FQMTG) for a perpetually free access to New Relic, which includes 100 GB of ingest per month and one Standard User license. You can also contact [New Relic Sales](https://newrelic.com/about/contact-us) for more details.

## Usage
> This solution includes a couple of AWS CloudFormation templates (`yml` files) you deploy in your AWS account that launches all the components necessary to integrate New Relic with your AWS accounts that you enroll or vend using the [Account Factory](https://aws.amazon.com/controltower/features/#Account_Factory) in your AWS Control Tower management account.

> The solution must be deployed in your AWS Control Tower management account, in the home [Region](https://aws.amazon.com/about-aws/global-infrastructure/regions_az/#Regions) of your Control Tower management account. This is the Region where your AWS Control Tower landing zone was set up.

> Build lambda zips and upload them along with template files to the S3 bucket that is reserved for this Quick Start

> `make build REGION=<YOUR_HOME_REGION>`

> `make upload PROFILE=<YOUR_AWS_PROFILE> REGION=<YOUR_HOME_REGION>`

> Next, create a Stack from [control-tower-customization.yml](templates/control-tower-customization.yml) template. This template requires parameters. You may create a file to store all parameters, so you can reference the file using `--parameters` argument, as shown below. Here the Region is `us-east-2`, replace it with your home Region.

```
aws cloudformation create-stack --region us-east-2 \
  --stack-name NewRelic-Control-Tower-Customization \
  --template-url https://newrelic-aws-quickstart.s3.us-east-2.amazonaws.com/control-tower/templates/control-tower-customization.yml \
  --parameters file://./templates/params.json \
  --capabilities CAPABILITY_NAMED_IAM
```

## Verifying the New Relic integration
> After you've deployed the solution, you can monitor your linked AWS accounts with New Relic. 

>1. Log in to your [New Relic account](https://one.newrelic.com/).
>2. Click the `Infrastructure` link on the top navigation bar. You will be taken to the `Infrastructure` page. If you happen to have access to multiple New Relic accounts, begin by choosing the New Relic account that you used for this implementation, from the dropdown list labeled `Infrastructure`, in the top left area of the screen. Otherwise, you should already see your New Relic account show up next to the label. Make sure the account ID matches the one you used in this implementation.
>3. Next, select the `AWS` tab and once your AWS accounts show up, click on `Account status dashboard` link to view the account dashboard.

## Tearing it Down
>If you intend to deploy the solution for testing and demonstration purposes and you don’t intend to use New Relic AWS integrations any longer, you can remove the stack.

## Support

New Relic hosts and moderates an online forum where customers can interact with New Relic employees as well as other customers to get help and share best practices. Like all official New Relic open source projects, there's a related Community topic in the New Relic Explorers Hub.

## Contributing
We encourage your contributions to improve [project name]! Keep in mind when you submit your pull request, you'll need to sign the CLA via the click-through using CLA-Assistant. You only have to sign the CLA one time per project.
If you have any questions, or to execute our corporate CLA, required if your contribution is on behalf of a company,  please drop us an email at opensource@newrelic.com.

## License
`AWS Control Tower Customization for Integration with New Relic` is licensed under the [Apache 2.0](http://apache.org/licenses/LICENSE-2.0.txt) License.
